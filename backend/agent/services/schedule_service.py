"""
Serviço de disponibilidade de agenda da Clínica Lúmina.
Consulta os slots cadastrados, filtra vagas disponíveis e
formata o contexto para injeção no prompt da IA.
"""
from datetime import date, datetime, timedelta
from sqlalchemy import select, func
from backend.system.database import AsyncSession
from backend.system.models.web_models import ScheduleSlotWeb, ClientWeb
from backend.system.logger import logger

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


async def get_available_slots(days_ahead: int = 7) -> list[dict]:
    """
    Retorna slots com vagas disponíveis nos próximos N dias.
    Cada item: {slot_id, weekday, date_str, date_iso, time_str, available}
    """
    today = date.today()
    available = []

    async with AsyncSession() as db:
        # Busca todos os slots ativos
        res = await db.execute(
            select(ScheduleSlotWeb)
            .where(ScheduleSlotWeb.is_active == True)
            .order_by(ScheduleSlotWeb.weekday, ScheduleSlotWeb.time_str)
        )
        slots = res.scalars().all()

        if not slots:
            return []

        # Para cada dia nos próximos N dias, verifica disponibilidade
        for delta in range(1, days_ahead + 1):
            check_date = today + timedelta(days=delta)
            weekday = check_date.weekday()  # 0=seg, 6=dom

            day_slots = [s for s in slots if s.weekday == weekday]
            for slot in day_slots:
                # Conta quantos clientes pendentes/confirmados já têm esse slot nessa data
                count_res = await db.execute(
                    select(func.count(ClientWeb.id)).where(
                        ClientWeb.slot_id == slot.id,
                        ClientWeb.slot_date == check_date,
                        ClientWeb.status.in_(["pending", "confirmed"])
                    )
                )
                booked = count_res.scalar() or 0
                free = slot.max_patients - booked

                if free > 0:
                    available.append({
                        "slot_id": slot.id,
                        "weekday": weekday,
                        "date_str": check_date.strftime("%d/%m"),
                        "date_iso": check_date.isoformat(),
                        "day_name": WEEKDAY_NAMES[weekday],
                        "time_str": slot.time_str,
                        "available": free,
                    })

    return available


async def get_available_slots_context(days_ahead: int = 7) -> str:
    """Retorna bloco de texto formatado para injeção no prompt da IA."""
    slots = await get_available_slots(days_ahead)
    if not slots:
        return (
            "\n\nAGENDA: Não há horários disponíveis nos próximos dias. "
            "Informe ao paciente e peça para entrar em contato novamente em breve."
        )

    lines = ["\n\nHorários Disponíveis para Agendamento (próximos dias):"]
    for s in slots:
        lines.append(f"- {s['day_name']} {s['date_str']} às {s['time_str']} [data_iso: {s['date_iso']}]")
    lines.append(
        "\nInstrução IMPORTANTE: Ofereça APENAS esses horários ao paciente. "
        "Não invente outros dias ou horários. Quando o paciente confirmar, "
        "inclua nos METADADOS: \"slot_date\": \"YYYY-MM-DD\" e \"slot_time\": \"HH:MM\"."
    )
    return "\n".join(lines)


async def reserve_slot(slot_id: int, slot_date: date, client_id: int) -> bool:
    """
    Tenta reservar um slot para um cliente.
    Retorna True se conseguiu, False se não há mais vaga (race condition).
    """
    async with AsyncSession() as db:
        # Revalida vaga em tempo real
        slot_res = await db.execute(select(ScheduleSlotWeb).where(ScheduleSlotWeb.id == slot_id))
        slot = slot_res.scalars().first()
        if not slot or not slot.is_active:
            return False

        count_res = await db.execute(
            select(func.count(ClientWeb.id)).where(
                ClientWeb.slot_id == slot_id,
                ClientWeb.slot_date == slot_date,
                ClientWeb.status.in_(["pending", "confirmed"])
            )
        )
        booked = count_res.scalar() or 0
        if booked >= slot.max_patients:
            logger.warning(f"Slot {slot_id} em {slot_date} sem vagas (race condition detectada).")
            return False

        # Atualiza o cliente com o slot reservado
        client_res = await db.execute(select(ClientWeb).where(ClientWeb.id == client_id))
        client = client_res.scalars().first()
        if client:
            client.slot_id = slot_id
            client.slot_date = slot_date
            await db.commit()
            logger.info(f"Slot {slot_id} em {slot_date} reservado para cliente {client_id}.")
            return True

    return False


async def find_slot_by_date_time(date_iso: str, time_str: str) -> ScheduleSlotWeb | None:
    """Busca o slot pelo par (data ISO, horário string)."""
    try:
        target_date = date.fromisoformat(date_iso)
        weekday = target_date.weekday()
    except ValueError:
        return None

    async with AsyncSession() as db:
        res = await db.execute(
            select(ScheduleSlotWeb).where(
                ScheduleSlotWeb.weekday == weekday,
                ScheduleSlotWeb.time_str == time_str,
                ScheduleSlotWeb.is_active == True,
            )
        )
        return res.scalars().first()
