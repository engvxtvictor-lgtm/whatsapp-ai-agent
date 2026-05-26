from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
import asyncio
from backend.system.database import get_db
from backend.system.dependencies import get_current_admin
from backend.system.models.web_models import AdminWeb, ClientWeb, ExamWeb, FollowupWeb

class AdminSchema(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    role: str
    avatar: Optional[str] = None
    
    class Config:
        from_attributes = True
router = APIRouter(prefix="/api")




from backend.agent.services import whatsapp
from backend.agent.services import session as sess
from backend.agent.services.followup_scheduler import run_followup_check
from backend.system.logger import logger




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
    slot_date: Optional[str] = None
    slot_time: Optional[str] = None
    upsell_success: bool = False
    upsell_service: Optional[str] = None
    status: str = "pending"
    ai_active: bool = True
    exam_id: Optional[int] = None
    exam_category: Optional[str] = None
    exam_price: Optional[float] = None
    needs_human: bool = False

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
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.exam), selectinload(ClientWeb.slot)).order_by(ClientWeb.id.desc())
    )
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
            slot_date=client.slot_date.isoformat() if client.slot_date else None,
            slot_time=client.slot.time_str if client.slot else None,
            upsell_success=client.upsell_success,
            upsell_service=client.upsell_service,
            status=client.status,
            ai_active=ai_active,
            exam_id=client.exam_id,
            exam_category=client.exam.category if client.exam else None,
            exam_price=client.exam.price if client.exam else None,
            needs_human=client.needs_human
        )
        
    enriched_clients = await asyncio.gather(*(enrich_client(c) for c in clients))
    return enriched_clients


@router.post("/clients", response_model=ClientSchema)
async def create_client(client_data: ClientSchema, db: AsyncSession = Depends(get_db)):
    service_name = client_data.service
    if client_data.exam_id:
        exam_res = await db.execute(select(ExamWeb).where(ExamWeb.id == client_data.exam_id))
        exam = exam_res.scalars().first()
        if exam:
            service_name = exam.name

    new_client = ClientWeb(
        name=client_data.name,
        cpf=client_data.cpf,
        phone=client_data.phone,
        source=client_data.source,
        service=service_name,
        profile_pic=client_data.profile_pic or f"https://api.dicebear.com/7.x/adventurer/svg?seed={client_data.name}",
        appointment_date=client_data.appointment_date,
        upsell_success=client_data.upsell_success,
        upsell_service=client_data.upsell_service,
        status=client_data.status or "pending",
        exam_id=client_data.exam_id,
        needs_human=client_data.needs_human
    )
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    
    # Recarrega com relacionamento
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.exam), selectinload(ClientWeb.slot)).where(ClientWeb.id == new_client.id)
    )
    new_client = result.scalars().first()
    
    client_schema = ClientSchema(
        id=new_client.id,
        name=new_client.name,
        cpf=new_client.cpf,
        phone=new_client.phone,
        source=new_client.source,
        service=new_client.service,
        profile_pic=new_client.profile_pic,
        appointment_date=new_client.appointment_date,
        slot_date=new_client.slot_date.isoformat() if new_client.slot_date else None,
        slot_time=new_client.slot.time_str if new_client.slot else None,
        upsell_success=new_client.upsell_success,
        upsell_service=new_client.upsell_service,
        status=new_client.status,
        ai_active=True,
        exam_id=new_client.exam_id,
        exam_category=new_client.exam.category if new_client.exam else None,
        exam_price=new_client.exam.price if new_client.exam else None,
        needs_human=new_client.needs_human
    )
    return client_schema


@router.put("/clients/{client_id}/confirm")
async def confirm_appointment(client_id: int, req: ConfirmRequestSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.slot)).where(ClientWeb.id == client_id)
    )
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")
        
    client.status = "confirmed"
    await db.commit()
    await db.refresh(client)
    
    # Formata data de agendamento usando slot_date se disponível
    appointment_text = client.appointment_date
    if client.slot_date and client.slot:
        appointment_text = f"{client.slot_date.strftime('%d/%m/%Y')} às {client.slot.time_str}"
        
    # Disparar mensagem de confirmacao estrita no WhatsApp (Resumo Final)
    confirm_msg = (
        f"✅ *Resumo Final de Agendamento*\n\n"
        f"Olá *{client.name}*, sua consulta foi confirmada com sucesso pelo(a) *{req.admin_name}*!\n\n"
        f"👤 *Dados do Cliente:*\n"
        f"• Nome: {client.name}\n"
    )
    
    if client.cpf:
        confirm_msg += f"• CPF: {client.cpf}\n"
        
    confirm_msg += f"• Telefone: {client.phone}\n\n"
    
    confirm_msg += (
        f"🦷 *Serviços Solicitados:*\n"
        f"• Original: {client.service}\n"
    )
    
    if client.upsell_success and client.upsell_service:
        confirm_msg += f"• Acrescentado: {client.upsell_service}\n"
        
    confirm_msg += (
        f"\n📅 *Data/Hora:* {appointment_text}\n\n"
        f"Te aguardamos na Clínica Lúmina! Qualquer dúvida, estamos à disposição. 🦷😊"
    )
    
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


@router.put("/clients/{client_id}/resolve-human")
async def resolve_human(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).where(ClientWeb.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")
    
    client.needs_human = False
    await db.commit()
    await db.refresh(client)
    return {"status": "ok", "client_id": client_id, "needs_human": False}


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).where(ClientWeb.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")
        
    # Deleta logs de follow-up do cliente
    await db.execute(delete(FollowupLogWeb).where(FollowupLogWeb.client_id == client_id))
    
    # Deleta a sessão no Redis associada ao telefone do cliente
    try:
        await sess.delete_session(client.phone)
    except Exception as e:
        logger.error(f"Erro ao deletar sessao no Redis para {client.phone}: {e}")
        
    # Deleta o cliente
    await db.delete(client)
    await db.commit()
    return {"status": "deleted", "id": client_id}



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


@router.post("/followups/run")
async def run_followups_now(bg: BackgroundTasks):
    """Dispara a verificação de follow-ups manualmente (útil para testes)."""
    bg.add_task(run_followup_check)
    return {"status": "ok", "message": "Verificação de follow-ups iniciada em background."}


class ExamSchema(BaseModel):
    id: Optional[int] = None
    name: str
    price: float
    category: str

    class Config:
        from_attributes = True


# Endpoints de Exames/Procedimentos
@router.get("/exams", response_model=List[ExamSchema])
async def get_exams(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExamWeb).order_by(ExamWeb.name.asc()))
    exams = result.scalars().all()
    return exams


@router.post("/exams", response_model=ExamSchema)
async def create_exam(data: ExamSchema, db: AsyncSession = Depends(get_db)):
    new_exam = ExamWeb(
        name=data.name,
        price=data.price,
        category=data.category
    )
    db.add(new_exam)
    await db.commit()
    await db.refresh(new_exam)
    return new_exam


@router.put("/exams/{exam_id}", response_model=ExamSchema)
async def update_exam(exam_id: int, data: ExamSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExamWeb).where(ExamWeb.id == exam_id))
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    
    exam.name = data.name
    exam.price = data.price
    exam.category = data.category
    await db.commit()
    await db.refresh(exam)
    return exam


@router.delete("/exams/{exam_id}")
async def delete_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExamWeb).where(ExamWeb.id == exam_id))
    exam = result.scalars().first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    
    await db.delete(exam)
    await db.commit()
    return {"status": "deleted", "id": exam_id}


