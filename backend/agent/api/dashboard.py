from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from backend.system.database import get_db
from backend.system.models.web_models import ClientWeb, AdminWeb
from backend.agent.services import whatsapp
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

    class Config:
        from_attributes = True


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
    return clients


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
        upsell_service=client_data.upsell_service
    )
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return new_client


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
        raise HTTPException(status_code=400, detail="A mensagem não pode ser vazia.")

    # Carrega os clientes selecionados do banco de dados
    result = await db.execute(select(ClientWeb).where(ClientWeb.id.in_(campaign.client_ids)))
    selected_clients = result.scalars().all()

    if not selected_clients:
        raise HTTPException(status_code=404, detail="Clientes selecionados não encontrados.")

    # Agenda o disparo assíncrono das mensagens
    bg.add_task(dispatch_campaign_messages, selected_clients, campaign.message)
    return {"status": "dispatched", "total_targets": len(selected_clients)}


async def dispatch_campaign_messages(clients: List[ClientWeb], template: str):
    logger.info(f"Iniciando envio de campanha para {len(clients)} clientes...")
    success_count = 0

    for client in clients:
        # Substitui placeholders dinamicamente
        msg_text = template.replace("[NOME]", client.name).replace("[SERVIÇO]", client.service)

        logger.info(f"Enviando campanha para {client.name} ({client.phone})...")
        success = await whatsapp.send_message(client.phone, msg_text)
        if success:
            success_count += 1

    logger.info(f"Campanha encerrada. Sucesso: {success_count}/{len(clients)}")
