from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import asyncio
from backend.system.database import get_db
from backend.system.models.web_models import ClientWeb, AdminWeb, FollowupWeb
from backend.agent.services import whatsapp
from backend.agent.services import session as sess
from backend.system.logger import logger

router = APIRouter(prefix="/api")


# Pydantic Schemas
class ClientSchema(BaseModel):
    id: Optional[int] = None
    name: str
    cpf: str
    phone: str
    source: str = "whatsapp"
    service: str
    profile_pic: Optional[str] = None
    
    # Novos campos de agendamento e upsell
    appointment_date: Optional[str] = None
    upsell_success: bool = False
    upsell_service: Optional[str] = None
    status: str = "pending"
    ai_active: bool = True

    class Config:
        from_attributes = True


class ConfirmRequestSchema(BaseModel):
    admin_name: str


class AdminSchema(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    role: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignSchema(BaseModel):
    client_ids: List[int]
    message: str


# Endpoints de Clientes
@router.get("/clients", response_model=List[ClientSchema])
async def get_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).order_by(ClientWeb.id.desc()))
    clients = result.scalars().all()
    
    async def enrich_client(client):
        try:
            session = await sess.get_session(client.phone)
            ai_active = not session.get("escalated", False)
        except Exception as e:
            logger.error(f"Erro ao buscar estado da IA no Redis para {client.phone}: {e}")
            ai_active = True
            
        return ClientSchema(
            id=client.id,
            name=client.name,
            cpf=client.cpf,
            phone=client.phone,
            source=client.source,
            service=client.service,
            profile_pic=client.profile_pic,
            appointment_date=client.appointment_date,
            upsell_success=client.upsell_success,
            upsell_service=client.upsell_service,
            status=client.status,
            ai_active=ai_active
        )
        
    enriched_clients = await asyncio.gather(*(enrich_client(c) for c in clients))
    return enriched_clients


@router.post("/clients", response_model=ClientSchema)
async def create_client(client_data: ClientSchema, db: AsyncSession = Depends(get_db)):
    new_client = ClientWeb(
        name=client_data.name,
        cpf=client_data.cpf,
        phone=client_data.phone,
        source=client_data.source,
        service=client_data.service,
        profile_pic=client_data.profile_pic or f"https://api.dicebear.com/7.x/adventurer/svg?seed={client_data.name}",
        appointment_date=client_data.appointment_date,
        upsell_success=client_data.upsell_success,
        upsell_service=client_data.upsell_service,
        status=client_data.status or "pending"
    )
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    
    client_schema = ClientSchema.from_orm(new_client)
    client_schema.ai_active = True
    return client_schema


@router.put("/clients/{client_id}/confirm")
async def confirm_appointment(client_id: int, req: ConfirmRequestSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).where(ClientWeb.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")
        
    client.status = "confirmed"
    await db.commit()
    await db.refresh(client)
    
    # Disparar mensagem de confirmacao estrita no WhatsApp
    confirm_msg = (
        f"✅ *Consulta Confirmada!*\n\n"
        f"Ola *{client.name}*, sua consulta de *{client.service}* foi confirmada com sucesso pelo(a) *{req.admin_name}*!\n"
        f"📅 *Data/Hora:* {client.appointment_date}\n"
    )
    if client.upsell_success and client.upsell_service:
        confirm_msg += f"➕ *Servico Adicional (Upsell):* {client.upsell_service}\n"
        
    confirm_msg += "\nTe aguardamos na Clinica Lumina! Qualquer duvida, estamos a disposicao. 🦷😊"
    
    await whatsapp.send_message(client.phone, confirm_msg)
    return {"status": "confirmed", "client_id": client_id}


@router.put("/clients/{client_id}/cancel")
async def cancel_appointment(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).where(ClientWeb.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")
        
    client.status = "cancelled"
    await db.commit()
    await db.refresh(client)
    
    # Disparar mensagem de indisponibilidade
    cancel_msg = (
        f"❌ *Agendamento Indisponivel*\n\n"
        f"Ola *{client.name}*, o dia/horario sugerido (*{client.appointment_date}*) para *{client.service}* infelizmente nao esta disponivel em nossa agenda.\n\n"
        f"Por favor, envie uma nova sugestao de dia e horario aqui no chat para podermos agendar sua consulta! 😊"
    )
    
    await whatsapp.send_message(client.phone, cancel_msg)
    return {"status": "cancelled", "client_id": client_id}


@router.put("/sessions/{phone}/toggle-ai")
async def toggle_ai(phone: str):
    try:
        session = await sess.get_session(phone)
        current_escalated = session.get("escalated", False)
        new_escalated = not current_escalated
        
        session["escalated"] = new_escalated
        if not new_escalated:
            session["ai_attempts"] = 0
            
        await sess.save_session(phone, session)
        return {"phone": phone, "ai_active": not new_escalated}
    except Exception as e:
        logger.error(f"Erro ao alternar IA para {phone}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao alternar estado da IA.")


# Endpoints de Administradores
@router.get("/admins", response_model=List[AdminSchema])
async def get_admins(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminWeb).order_by(AdminWeb.id.desc()))
    admins = result.scalars().all()
    return admins


@router.post("/admins", response_model=AdminSchema)
async def create_admin(admin_data: AdminSchema, db: AsyncSession = Depends(get_db)):
    new_admin = AdminWeb(
        name=admin_data.name,
        email=admin_data.email,
        role=admin_data.role,
        avatar=admin_data.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={admin_data.name}"
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return new_admin


# Rota de Envio de Campanhas
@router.post("/campaigns")
async def send_campaign(campaign: CampaignSchema, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if not campaign.client_ids:
        raise HTTPException(status_code=400, detail="Nenhum cliente selecionado.")
    if not campaign.message.strip():
        raise HTTPException(status_code=400, detail="A mensagem nao pode ser vazia.")

    # Carrega os clientes selecionados do banco de dados
    result = await db.execute(select(ClientWeb).where(ClientWeb.id.in_(campaign.client_ids)))
    selected_clients = result.scalars().all()

    if not selected_clients:
        raise HTTPException(status_code=404, detail="Clientes selecionados nao encontrados.")

    # Agenda o disparo assincrono das mensagens
    bg.add_task(dispatch_campaign_messages, selected_clients, campaign.message)
    return {"status": "dispatched", "total_targets": len(selected_clients)}


async def dispatch_campaign_messages(clients: List[ClientWeb], template: str):
    logger.info(f"Iniciando envio de campanha para {len(clients)} clientes...")
    success_count = 0

    for client in clients:
        # Substitui placeholders dinamicamente
        msg_text = template.replace("[NOME]", client.name).replace("[SERVICO]", client.service)

        logger.info(f"Enviando campanha para {client.name} ({client.phone})...")
        success = await whatsapp.send_message(client.phone, msg_text)
        if success:
            success_count += 1

    logger.info(f"Campanha encerrada. Sucesso: {success_count}/{len(clients)}")


class FollowupSchema(BaseModel):
    id: Optional[int] = None
    name: str
    service: str
    delay_days: int
    message_template: str
    is_active: bool = True

    class Config:
        from_attributes = True


# Endpoints de Follow-Up
@router.get("/followups", response_model=List[FollowupSchema])
async def get_followups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowupWeb).order_by(FollowupWeb.id.asc()))
    followups = result.scalars().all()
    return followups


@router.post("/followups", response_model=FollowupSchema)
async def create_followup(data: FollowupSchema, db: AsyncSession = Depends(get_db)):
    new_followup = FollowupWeb(
        name=data.name,
        service=data.service,
        delay_days=data.delay_days,
        message_template=data.message_template,
        is_active=data.is_active
    )
    db.add(new_followup)
    await db.commit()
    await db.refresh(new_followup)
    return new_followup


@router.put("/followups/{followup_id}/toggle")
async def toggle_followup(followup_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowupWeb).where(FollowupWeb.id == followup_id))
    followup = result.scalars().first()
    if not followup:
        raise HTTPException(status_code=404, detail="Regra de follow-up nao encontrada.")
    
    followup.is_active = not followup.is_active
    await db.commit()
    await db.refresh(followup)
    return {"status": "ok", "id": followup_id, "is_active": followup.is_active}


@router.delete("/followups/{followup_id}")
async def delete_followup(followup_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowupWeb).where(FollowupWeb.id == followup_id))
    followup = result.scalars().first()
    if not followup:
        raise HTTPException(status_code=404, detail="Regra de follow-up nao encontrada.")
    
    await db.delete(followup)
    await db.commit()
    return {"status": "deleted", "id": followup_id}

