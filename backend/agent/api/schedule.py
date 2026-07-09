"""API de gerenciamento da grade de horários (Schedule Slots)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from backend.system.database import get_db
from backend.system.models.web_models import ScheduleSlotWeb
from backend.agent.services.schedule_service import get_available_slots, is_business_slot
from backend.system.logger import logger

router = APIRouter(prefix="/api/slots")

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


class SlotSchema(BaseModel):
    id: Optional[int] = None
    weekday: int
    time_str: str
    max_patients: int = 1
    is_active: bool = True
    weekday_name: Optional[str] = None

    class Config:
        from_attributes = True


class SlotAvailableSchema(BaseModel):
    slot_id: int
    weekday: int
    day_name: str
    date_str: str
    date_iso: str
    time_str: str
    available: int


@router.get("", response_model=List[SlotSchema])
async def list_slots(db: AsyncSession = Depends(get_db)):
    """Lista todos os slots configurados na grade."""
    res = await db.execute(
        select(ScheduleSlotWeb).order_by(ScheduleSlotWeb.weekday, ScheduleSlotWeb.time_str)
    )
    slots = res.scalars().all()
    return [
        SlotSchema(
            id=s.id,
            weekday=s.weekday,
            time_str=s.time_str,
            max_patients=s.max_patients,
            is_active=s.is_active,
            weekday_name=WEEKDAY_NAMES[s.weekday],
        )
        for s in slots
    ]


@router.get("/available", response_model=List[SlotAvailableSchema])
async def list_available_slots(days: int = 7):
    """Retorna slots com vagas nos próximos N dias."""
    return await get_available_slots(days_ahead=days)


@router.post("", response_model=SlotSchema)
async def create_slot(data: SlotSchema, db: AsyncSession = Depends(get_db)):
    """Cria um novo slot na grade de horários."""
    if not (0 <= data.weekday <= 6):
        raise HTTPException(status_code=400, detail="weekday deve ser entre 0 (seg) e 6 (dom).")
    if not is_business_slot(data.weekday, data.time_str):
        raise HTTPException(
            status_code=400,
            detail="Horário fora do funcionamento da clínica: segunda a sexta 08h às 12h e 14h às 18h; sábado 08h às 12h.",
        )

    new_slot = ScheduleSlotWeb(
        weekday=data.weekday,
        time_str=data.time_str,
        max_patients=data.max_patients,
        is_active=data.is_active,
    )
    db.add(new_slot)
    await db.commit()
    await db.refresh(new_slot)
    logger.info(f"Slot criado: {WEEKDAY_NAMES[new_slot.weekday]} às {new_slot.time_str}")
    return SlotSchema(
        id=new_slot.id,
        weekday=new_slot.weekday,
        time_str=new_slot.time_str,
        max_patients=new_slot.max_patients,
        is_active=new_slot.is_active,
        weekday_name=WEEKDAY_NAMES[new_slot.weekday],
    )


@router.put("/{slot_id}/toggle", response_model=SlotSchema)
async def toggle_slot(slot_id: int, db: AsyncSession = Depends(get_db)):
    """Ativa ou desativa um slot."""
    res = await db.execute(select(ScheduleSlotWeb).where(ScheduleSlotWeb.id == slot_id))
    slot = res.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot não encontrado.")
    slot.is_active = not slot.is_active
    await db.commit()
    await db.refresh(slot)
    return SlotSchema(
        id=slot.id,
        weekday=slot.weekday,
        time_str=slot.time_str,
        max_patients=slot.max_patients,
        is_active=slot.is_active,
        weekday_name=WEEKDAY_NAMES[slot.weekday],
    )


@router.delete("/{slot_id}")
async def delete_slot(slot_id: int, db: AsyncSession = Depends(get_db)):
    """Remove um slot da grade."""
    res = await db.execute(select(ScheduleSlotWeb).where(ScheduleSlotWeb.id == slot_id))
    slot = res.scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot não encontrado.")
    await db.delete(slot)
    await db.commit()
    return {"status": "deleted", "id": slot_id}
