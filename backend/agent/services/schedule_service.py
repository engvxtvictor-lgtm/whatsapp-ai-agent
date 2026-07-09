"""
Serviço de disponibilidade de agenda da Clínica Lúmina.
Consulta os slots cadastrados, filtra vagas disponíveis e
formata o contexto para injeção no prompt da IA.
"""
import re
import unicodedata
from datetime import date, datetime, timedelta
from sqlalchemy import select, func
from backend.system.database import AsyncSession
from backend.system.models.web_models import ScheduleSlotWeb, ClientWeb
from backend.system.logger import logger

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
WEEKDAY_ALIASES = {
    "segunda": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terça": 1,
    "terca-feira": 1,
    "terça-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

BUSINESS_HOURS_TEXT = "segunda a sexta, das 08h00 às 12h00 e das 14h00 às 18h00; sábado, das 08h00 às 12h00"
WEEKDAY_APPOINTMENT_TIMES = {
    "08:00", "09:00", "10:00", "11:00",
    "14:00", "15:00", "16:00", "17:00", "18:00",
}
SATURDAY_APPOINTMENT_TIMES = {"08:00", "09:00", "10:00", "11:00"}
ALLOWED_APPOINTMENT_TIMES = WEEKDAY_APPOINTMENT_TIMES | SATURDAY_APPOINTMENT_TIMES


def is_business_time(time_str: str | None) -> bool:
    """Valida horarios reais de atendimento da clinica."""
    normalized = normalize_time(time_str)
    return bool(normalized and normalized in ALLOWED_APPOINTMENT_TIMES)


def is_business_day(slot_date: date | None) -> bool:
    return bool(slot_date and 0 <= slot_date.weekday() <= 5)


def is_business_slot(weekday: int | None, time_str: str | None) -> bool:
    normalized = normalize_time(time_str)
    if normalized is None or weekday is None:
        return False
    if 0 <= weekday <= 4:
        return normalized in WEEKDAY_APPOINTMENT_TIMES
    if weekday == 5:
        return normalized in SATURDAY_APPOINTMENT_TIMES
    return False


def business_hours_message() -> str:
    return f"Nosso horário de funcionamento é de {BUSINESS_HOURS_TEXT}."


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
                if not is_business_slot(weekday, slot.time_str):
                    continue
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
        if not slot or not slot.is_active or not is_business_day(slot_date) or not is_business_slot(slot_date.weekday(), slot.time_str):
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

    if not is_business_day(target_date) or not is_business_slot(weekday, time_str):
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


def normalize_time(time_text: str | None) -> str | None:
    """Normaliza horarios como 'as 10', '10h' e '10:00' para HH:MM."""
    if not time_text:
        return None
    text = _strip_accents(time_text.lower().strip())
    text = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", text)
    match = re.search(r"\b(\d{1,2})[:h](\d{2})?\b", text)
    if not match:
        match = re.search(r"\b(?:as|às|a)\s+(\d{1,2})(?:\s*h)?\b", text)
    if not match:
        match = re.search(r"\b(\d{1,2})\s*(?:hora|horas)\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute_text = match.group(2) if len(match.groups()) >= 2 else None
    minute = int(minute_text or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def next_date_for_weekday(weekday: int, from_date: date | None = None) -> date:
    """Retorna a proxima data futura para o dia da semana informado."""
    base = from_date or date.today()
    delta = (weekday - base.weekday()) % 7
    if delta == 0:
        delta = 7
    return base + timedelta(days=delta)


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def parse_appointment_text(text: str | None, from_date: date | None = None) -> tuple[date | None, str | None]:
    """
    Extrai data e horario de textos livres gerados pela IA ou digitados pelo paciente.
    Suporta '15/06 as 10', '15/06/2026 10:00', 'segunda as 10',
    'hoje', 'amanha' e variantes.
    """
    if not text:
        return None, None

    base = from_date or date.today()
    raw = text.lower()
    time_str = normalize_time(raw)
    parsed_date = None

    date_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", raw)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year_text = date_match.group(3)
        year = int(year_text) if year_text else base.year
        if year < 100:
            year += 2000
        try:
            parsed_date = date(year, month, day)
        except ValueError:
            parsed_date = None

    normalized = _strip_accents(raw)

    if not parsed_date:
        if re.search(r"\bdepois\s+d[ae]\s+amanha\b|\bdepois\s+de\s+amanha\b", normalized):
            parsed_date = base + timedelta(days=2)
        elif re.search(r"\bamanha\b", normalized):
            parsed_date = base + timedelta(days=1)
        elif re.search(r"\bhoje\b", normalized):
            parsed_date = base

    if not parsed_date:
        for alias, weekday in WEEKDAY_ALIASES.items():
            alias_norm = _strip_accents(alias)
            if re.search(rf"\b{re.escape(alias_norm)}\b", normalized):
                parsed_date = next_date_for_weekday(weekday, base)
                break

    return parsed_date, time_str


async def resolve_slot_from_text(text: str | None) -> tuple[ScheduleSlotWeb | None, date | None, str | None]:
    """Resolve slot cadastrado a partir de texto livre contendo data e horario."""
    slot_date, slot_time = parse_appointment_text(text)
    if not slot_date or not slot_time:
        return None, slot_date, slot_time
    slot = await find_slot_by_date_time(slot_date.isoformat(), slot_time)
    return slot, slot_date, slot_time
