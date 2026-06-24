from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
import asyncio
import os
import uuid
import aiofiles
import unicodedata
from datetime import date
from backend.system.database import get_db
from backend.system.dependencies import get_current_admin
from backend.system.models.web_models import AdminWeb, ClientWeb, ExamWeb, FollowupWeb, FollowupLogWeb, ScheduleSlotWeb

class AdminSchema(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    password: Optional[str] = None
    role: str
    avatar: Optional[str] = None
    
    class Config:
        from_attributes = True
router = APIRouter(prefix="/api")




from backend.agent.services import whatsapp
from backend.agent.services import session as sess
from backend.agent.services import schedule_service
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
    password: Optional[str] = None
    role: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignSchema(BaseModel):
    client_ids: List[int]
    message: str


GENERIC_SERVICE_NAMES = {
    "consulta", "consulta odontologica", "consulta odontológica", "avaliacao",
    "avaliação", "atendimento", "atendimento humano", "em andamento",
    "em andamento...", "procedimento", "servico", "serviço", "exame",
    "aguardando procedimento"
}


def _normalize_label(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = " ".join(text.replace(".", " ").replace("-", " ").split())
    return text


def _is_generic_service(value: str | None) -> bool:
    normalized = _normalize_label(value)
    return not normalized or normalized in {_normalize_label(item) for item in GENERIC_SERVICE_NAMES}


async def resolve_client_slot_data(client_data: ClientSchema):
    slot_id = None
    slot_date_obj = None

    if client_data.slot_date:
        try:
            slot_date_obj = date.fromisoformat(client_data.slot_date)
        except ValueError:
            slot_date_obj = None

    if slot_date_obj and client_data.slot_time:
        slot = await schedule_service.find_slot_by_date_time(slot_date_obj.isoformat(), client_data.slot_time)
        if slot:
            slot_id = slot.id
    elif client_data.appointment_date:
        slot, parsed_slot_date, parsed_slot_time = await schedule_service.resolve_slot_from_text(client_data.appointment_date)
        if parsed_slot_date:
            slot_date_obj = parsed_slot_date
        if slot:
            slot_id = slot.id

    return slot_id, slot_date_obj


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
            service=client.exam.name if client.exam else client.service,
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
    slot_id, slot_date_obj = await resolve_client_slot_data(client_data)

    new_client = ClientWeb(
        name=client_data.name,
        cpf=client_data.cpf,
        phone=client_data.phone,
        source=client_data.source,
        service=service_name,
        appointment_date=client_data.appointment_date,
        slot_id=slot_id,
        slot_date=slot_date_obj,
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
        service=new_client.exam.name if new_client.exam else new_client.service,
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


@router.put("/clients/{client_id}", response_model=ClientSchema)
async def update_client(client_id: int, client_data: ClientSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientWeb).options(selectinload(ClientWeb.exam), selectinload(ClientWeb.slot)).where(ClientWeb.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
        
    service_name = client_data.service
    if client_data.exam_id:
        exam_res = await db.execute(select(ExamWeb).where(ExamWeb.id == client_data.exam_id))
        exam = exam_res.scalars().first()
        if exam:
            service_name = exam.name
    slot_id, slot_date_obj = await resolve_client_slot_data(client_data)

    client.name = client_data.name
    client.cpf = client_data.cpf
    client.phone = client_data.phone
    client.service = service_name
    client.appointment_date = client_data.appointment_date
    client.slot_id = slot_id
    client.slot_date = slot_date_obj
    client.upsell_success = client_data.upsell_success
    client.upsell_service = client_data.upsell_service
    client.status = client_data.status or client.status
    client.exam_id = client_data.exam_id
    client.needs_human = client_data.needs_human
    
    await db.commit()
    await db.refresh(client)
    
    # Reload with relationships
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.exam), selectinload(ClientWeb.slot)).where(ClientWeb.id == client.id)
    )
    client = result.scalars().first()
    
    return ClientSchema(
        id=client.id,
        name=client.name,
        cpf=client.cpf,
        phone=client.phone,
        source=client.source,
        service=client.exam.name if client.exam else client.service,
        appointment_date=client.appointment_date,
        slot_date=client.slot_date.isoformat() if client.slot_date else None,
        slot_time=client.slot.time_str if client.slot else None,
        upsell_success=client.upsell_success,
        upsell_service=client.upsell_service,
        status=client.status,
        ai_active=client_data.ai_active,
        exam_id=client.exam_id,
        exam_category=client.exam.category if client.exam else None,
        exam_price=client.exam.price if client.exam else None,
        needs_human=client.needs_human
    )


@router.put("/clients/{client_id}/confirm")
async def confirm_appointment(client_id: int, req: ConfirmRequestSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.slot), selectinload(ClientWeb.exam)).where(ClientWeb.id == client_id)
    )
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    if _is_generic_service(client.service):
        raise HTTPException(
            status_code=400,
            detail="Informe o procedimento/serviço real antes de confirmar este agendamento."
        )

    if not client.slot_date and client.appointment_date:
        found_slot, parsed_slot_date, parsed_slot_time = await schedule_service.resolve_slot_from_text(client.appointment_date)
        if parsed_slot_date:
            client.slot_date = parsed_slot_date
        if found_slot:
            client.slot_id = found_slot.id
            client.slot = found_slot
        if parsed_slot_date and parsed_slot_time:
            client.appointment_date = f"{parsed_slot_date.strftime('%d/%m/%Y')} às {parsed_slot_time}"

    if not client.slot_date or not client.appointment_date or _normalize_label(client.appointment_date) == "pendente":
        raise HTTPException(
            status_code=400,
            detail="Informe uma data e horario validos antes de confirmar este agendamento."
        )

    if client.exam:
        client.service = client.exam.name

    client.status = "confirmed"
    await db.commit()
    result = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.slot), selectinload(ClientWeb.exam)).where(ClientWeb.id == client_id)
    )
    client = result.scalars().first()
    
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


import bcrypt

@router.post("/admins", response_model=AdminSchema)
async def create_admin(admin_data: AdminSchema, db: AsyncSession = Depends(get_db)):
    from backend.system.auth import get_password_hash
    password = admin_data.password if admin_data.password else "senha123"
    hashed_pw = get_password_hash(password)
    new_admin = AdminWeb(
        name=admin_data.name,
        email=admin_data.email,
        password_hash=hashed_pw,
        role=admin_data.role,
        avatar=admin_data.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={admin_data.name}"
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return new_admin


@router.put("/admins/{admin_id}", response_model=AdminSchema)
async def update_admin(admin_id: int, admin_data: AdminSchema, db: AsyncSession = Depends(get_db)):
    from backend.system.auth import get_password_hash
    result = await db.execute(select(AdminWeb).where(AdminWeb.id == admin_id))
    admin = result.scalars().first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador nao encontrado.")
    
    admin.name = admin_data.name
    admin.email = admin_data.email
    admin.role = admin_data.role
    if admin_data.avatar:
        admin.avatar = admin_data.avatar
    if admin_data.password:
        admin.password_hash = get_password_hash(admin_data.password)
        
    await db.commit()
    await db.refresh(admin)
    return admin


@router.delete("/admins/{admin_id}")
async def delete_admin(admin_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminWeb).where(AdminWeb.id == admin_id))
    admin = result.scalars().first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador nao encontrado.")
    
    await db.delete(admin)
    await db.commit()
    return {"status": "deleted", "id": admin_id}


@router.post("/admins/{admin_id}/avatar", response_model=AdminSchema)
async def upload_admin_avatar(admin_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminWeb).where(AdminWeb.id == admin_id))
    admin = result.scalars().first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador não encontrado.")

    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    avatars_dir = os.path.join("uploads", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    filepath = os.path.join(avatars_dir, filename)

    async with aiofiles.open(filepath, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    avatar_url = f"/uploads/avatars/{filename}"
    admin.avatar = avatar_url
    await db.commit()
    await db.refresh(admin)
    return admin


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


class FollowupClientSummarySchema(BaseModel):
    id: int
    name: str
    phone: str
    status: str
    appointment_date: Optional[str] = None
    sent_status: str
    sent_at: Optional[str] = None


class FollowupSchema(BaseModel):
    id: Optional[int] = None
    name: str
    service: str
    delay_days: int
    message_template: str
    is_active: bool = True
    is_recurring: bool = False
    recurrence_interval: Optional[int] = 0
    affected_clients: List[FollowupClientSummarySchema] = []

    class Config:
        from_attributes = True


async def get_followups_with_affected(db: AsyncSession, followup_id: Optional[int] = None):
    # Busca regras
    if followup_id:
        query = select(FollowupWeb).where(FollowupWeb.id == followup_id)
    else:
        query = select(FollowupWeb).order_by(FollowupWeb.id.asc())
        
    result = await db.execute(query)
    followups = result.scalars().all()

    # Busca clientes confirmados
    client_res = await db.execute(
        select(ClientWeb).options(selectinload(ClientWeb.slot)).where(ClientWeb.status == "confirmed")
    )
    clients = client_res.scalars().all()

    # Busca logs de follow-up
    log_res = await db.execute(select(FollowupLogWeb))
    logs = log_res.scalars().all()
    logs_map = {(log.client_id, log.followup_id): log.sent_at for log in logs}

    response_data = []
    for f in followups:
        affected = []
        for c in clients:
            # Match lógico idêntico ao do scheduler
            service_match = (
                f.service.lower() in c.service.lower()
                or c.service.lower() in f.service.lower()
            )
            if service_match:
                sent_at = logs_map.get((c.id, f.id))
                sent_status = "Enviado" if sent_at else "Pendente"
                
                # Formata data da consulta
                appointment_text = c.appointment_date
                if c.slot_date and c.slot:
                    appointment_text = f"{c.slot_date.strftime('%d/%m/%Y')} às {c.slot.time_str}"

                affected.append(
                    FollowupClientSummarySchema(
                        id=c.id,
                        name=c.name,
                        phone=c.phone,
                        status=c.status,
                        appointment_date=appointment_text,
                        sent_status=sent_status,
                        sent_at=sent_at.strftime('%d/%m/%Y %H:%M') if sent_at else None
                    )
                )
        
        response_data.append(
            FollowupSchema(
                id=f.id,
                name=f.name,
                service=f.service,
                delay_days=f.delay_days,
                message_template=f.message_template,
                is_active=f.is_active,
                is_recurring=f.is_recurring,
                recurrence_interval=f.recurrence_interval,
                affected_clients=affected
            )
        )
        
    if followup_id:
        return response_data[0] if response_data else None
    return response_data


# Endpoints de Follow-Up
@router.get("/followups", response_model=List[FollowupSchema])
async def get_followups(db: AsyncSession = Depends(get_db)):
    return await get_followups_with_affected(db)


@router.post("/followups", response_model=FollowupSchema)
async def create_followup(data: FollowupSchema, db: AsyncSession = Depends(get_db)):
    new_followup = FollowupWeb(
        name=data.name,
        service=data.service,
        delay_days=data.delay_days,
        message_template=data.message_template,
        is_active=data.is_active,
        is_recurring=data.is_recurring,
        recurrence_interval=data.recurrence_interval
    )
    db.add(new_followup)
    await db.commit()
    return await get_followups_with_affected(db, new_followup.id)


@router.put("/followups/{followup_id}/toggle", response_model=FollowupSchema)
async def toggle_followup(followup_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowupWeb).where(FollowupWeb.id == followup_id))
    followup = result.scalars().first()
    if not followup:
        raise HTTPException(status_code=404, detail="Regra de follow-up nao encontrada.")
    
    followup.is_active = not followup.is_active
    await db.commit()
    return await get_followups_with_affected(db, followup_id)


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


OFFICIAL_EXAMS = [
    ("Extração Complexa (Siso)", 300.00, "Cirurgia"),
    ("Extração Simples", 120.00, "Cirurgia"),
    ("Placa para Bruxismo", 450.00, "Clínico Geral"),
    ("Restauração", 80.00, "Clínico Geral"),
    ("Radiografia Periapical", 35.00, "Diagnóstico"),
    ("Tratamento de Canal", 600.00, "Endodontia"),
    ("Clareamento (por sessão)", 250.00, "Estética"),
    ("Facetas (por dente)", 250.00, "Estética"),
    ("Remoção de Facetas", 300.00, "Estética"),
    ("Implante", 2800.00, "Implantodontia"),
    ("Consulta + Aplicação de Flúor Infantil", 50.00, "Odontopediatria"),
    ("Extração Infantil", 90.00, "Odontopediatria"),
    ("Restauração Infantil", 70.00, "Odontopediatria"),
    ("Contenção Ortodôntica Inferior", 200.00, "Ortodontia"),
    ("Contenção Ortodôntica Superior", 250.00, "Ortodontia"),
    ("Manutenção Aparelho", 90.00, "Ortodontia"),
    ("Gengivoplastia (por dente)", 200.00, "Periodontia"),
    ("Raspagem (Limpeza)", 120.00, "Prevenção"),
    ("Pino + Coroa", 500.00, "Prótese"),
    ("Prótese Dentária", 950.00, "Prótese"),
]


async def ensure_official_exams(db: AsyncSession):
    result = await db.execute(select(ExamWeb))
    existing_by_name = {exam.name.strip().lower(): exam for exam in result.scalars().all()}
    missing = [
        ExamWeb(name=name, price=price, category=category)
        for name, price, category in OFFICIAL_EXAMS
        if name.strip().lower() not in existing_by_name
    ]
    if missing:
        db.add_all(missing)
        await db.commit()


# Endpoints de Exames/Procedimentos
@router.get("/exams", response_model=List[ExamSchema])
async def get_exams(db: AsyncSession = Depends(get_db)):
    await ensure_official_exams(db)
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



# ── Endpoints de Slots (Agenda / Horários) ──────────────────────────────

class ClientSummarySchema(BaseModel):
    id: int
    name: str
    phone: str
    status: str

    class Config:
        from_attributes = True


class SlotSchema(BaseModel):
    id: Optional[int] = None
    weekday: int
    time_str: str
    max_patients: int = 1
    is_active: bool = True
    clients: List[ClientSummarySchema] = []

    class Config:
        from_attributes = True


@router.get("/slots", response_model=List[SlotSchema])
async def get_slots(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScheduleSlotWeb)
        .options(selectinload(ScheduleSlotWeb.clients))
        .order_by(ScheduleSlotWeb.weekday, ScheduleSlotWeb.time_str)
    )
    slots = result.scalars().all()
    return [slot for slot in slots if schedule_service.is_business_time(slot.time_str)]


@router.post("/slots", response_model=SlotSchema)
async def create_slot(data: SlotSchema, db: AsyncSession = Depends(get_db)):
    if not schedule_service.is_business_time(data.time_str):
        raise HTTPException(
            status_code=400,
            detail="Horário fora do funcionamento da clínica: 08h às 12h e 14h às 18h.",
        )

    new_slot = ScheduleSlotWeb(
        weekday=data.weekday,
        time_str=data.time_str,
        max_patients=data.max_patients,
        is_active=data.is_active
    )
    db.add(new_slot)
    await db.commit()
    
    # Reload with clients relationship loaded
    result = await db.execute(
        select(ScheduleSlotWeb)
        .options(selectinload(ScheduleSlotWeb.clients))
        .where(ScheduleSlotWeb.id == new_slot.id)
    )
    slot_loaded = result.scalars().first()
    return slot_loaded


@router.put("/slots/{slot_id}/toggle", response_model=SlotSchema)
async def toggle_slot(slot_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScheduleSlotWeb)
        .options(selectinload(ScheduleSlotWeb.clients))
        .where(ScheduleSlotWeb.id == slot_id)
    )
    slot = result.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Horário não encontrado.")
    slot.is_active = not slot.is_active
    await db.commit()
    
    # Reload with clients relationship loaded
    result = await db.execute(
        select(ScheduleSlotWeb)
        .options(selectinload(ScheduleSlotWeb.clients))
        .where(ScheduleSlotWeb.id == slot_id)
    )
    slot_loaded = result.scalars().first()
    return slot_loaded


@router.delete("/slots/{slot_id}")
async def delete_slot(slot_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduleSlotWeb).where(ScheduleSlotWeb.id == slot_id))
    slot = result.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Horário não encontrado.")
    await db.delete(slot)
    await db.commit()
    return {"status": "deleted", "id": slot_id}
