"""
Scheduler de Follow-Up Automático da Clínica Lúmina.

Roda todo dia às 09:00 (horário local) e verifica se algum cliente
confirmado atingiu o prazo de um follow-up ativo. Se sim, dispara
a mensagem no WhatsApp automaticamente.
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from backend.system.database import AsyncSession
from backend.system.models.web_models import (
    AppointmentReminderLogWeb,
    ClientWeb,
    FollowupWeb,
    FollowupLogWeb,
)
from backend.agent.services import whatsapp
from backend.system.logger import logger

CLINIC_TIMEZONE = ZoneInfo("America/Sao_Paulo")


# Formatos de data aceitos no campo appointment_date dos clientes
_DATE_FORMATS = [
    "%d/%m/%Y às %H:%M",
    "%d/%m/%Y as %H:%M",
    "%d/%m/%Y às %Hh%M",
    "%d/%m/%Y as %Hh%M",
    "%d/%m/%Y",
    "%d/%m/%y",
]


def _parse_appointment_date(date_str: str) -> datetime | None:
    """Tenta converter o campo appointment_date para um objeto datetime."""
    if not date_str:
        return None
    # Remove espaços extras e normaliza
    date_str = date_str.strip()
    # Tenta extrair só a data (dd/mm/yyyy) caso exista
    match = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", date_str)
    if not match:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    # Fallback: só a data extraída
    try:
        return datetime.strptime(match.group(), "%d/%m/%Y")
    except ValueError:
        pass
    try:
        return datetime.strptime(match.group(), "%d/%m/%y")
    except ValueError:
        pass
    return None


async def run_followup_check():
    """
    Verifica todos os clientes confirmados e dispara follow-ups
    cujo prazo (delay_days desde a consulta) já foi atingido.
    """
    logger.info("⏰ Scheduler: iniciando verificação de follow-ups...")
    today = datetime.utcnow().date()
    sent_count = 0

    async with AsyncSession() as db:
        # Busca todos os follow-ups ativos
        fu_res = await db.execute(
            select(FollowupWeb).where(FollowupWeb.is_active == True)
        )
        followups = fu_res.scalars().all()

        if not followups:
            logger.info("Scheduler: nenhuma regra de follow-up ativa encontrada.")
            return

        # Busca todos os clientes confirmados
        cl_res = await db.execute(
            select(ClientWeb).where(ClientWeb.status == "confirmed")
        )
        clients = cl_res.scalars().all()

        for client in clients:
            if client.slot_date:
                appointment_date = client.slot_date
            else:
                appointment_dt = _parse_appointment_date(client.appointment_date or "")
                if not appointment_dt:
                    continue
                appointment_date = appointment_dt.date()

            for followup in followups:
                # Verifica se o serviço do cliente bate com o gatilho do follow-up
                service_match = (
                    followup.service.lower() in client.service.lower()
                    or client.service.lower() in followup.service.lower()
                )
                if not service_match:
                    continue

                # Busca logs de envio anteriores para esse cliente e followup, ordenados do mais recente
                log_res = await db.execute(
                    select(FollowupLogWeb)
                    .where(
                        and_(
                            FollowupLogWeb.client_id == client.id,
                            FollowupLogWeb.followup_id == followup.id,
                        )
                    )
                    .order_by(FollowupLogWeb.sent_at.desc())
                )
                sent_logs = log_res.scalars().all()

                # Determina data alvo
                is_rec = getattr(followup, "is_recurring", False)
                rec_val = getattr(followup, "recurrence_interval", 0) or 0

                if is_rec and rec_val > 0:
                    if sent_logs:
                        # Se já foi enviado alguma vez, o próximo envio é após 'recurrence_interval' dias do último envio
                        last_sent_date = sent_logs[0].sent_at.date()
                        target_date = last_sent_date + timedelta(days=rec_val)
                    else:
                        # Primeiro envio do recorrente respeita o delay inicial
                        target_date = appointment_date + timedelta(days=followup.delay_days)
                else:
                    # Envio único
                    if sent_logs:
                        # Já foi enviado, pula
                        continue
                    target_date = appointment_date + timedelta(days=followup.delay_days)

                # Só dispara se hoje é o dia certo (ou passou — envia com até 3 dias de atraso)
                days_overdue = (today - target_date).days
                if not (0 <= days_overdue <= 3):
                    continue

                # Monta e envia a mensagem
                msg = (
                    followup.message_template
                    .replace("[NOME]", client.name)
                    .replace("[SERVIÇO]", client.service)
                    .replace("[SERVICO]", client.service)
                )

                logger.info(
                    f"📤 Enviando follow-up '{followup.name}' para {client.name} ({client.phone[:6]}***)"
                )
                success = await whatsapp.send_message(client.phone, msg)

                if success:
                    # Registra no log para não enviar novamente
                    db.add(FollowupLogWeb(
                        client_id=client.id,
                        followup_id=followup.id,
                    ))
                    await db.commit()
                    sent_count += 1
                    logger.info(f"✅ Follow-up registrado para {client.name}.")
                else:
                    logger.warning(f"⚠️ Falha ao enviar follow-up para {client.phone[:6]}***.")

    logger.info(f"⏰ Scheduler: verificação concluída. {sent_count} follow-up(s) enviado(s).")


def _get_client_schedule(client: ClientWeb):
    """Retorna data e horario normalizados do agendamento."""
    if client.slot_date and client.slot and client.slot.time_str:
        return client.slot_date, client.slot.time_str

    appointment_dt = _parse_appointment_date(client.appointment_date or "")
    if not appointment_dt:
        return None
    return appointment_dt.date(), appointment_dt.strftime("%H:%M")


async def _run_appointment_reminder_check(reminder_type: str):
    """Envia uma vez o lembrete do tipo solicitado."""
    today = datetime.now(CLINIC_TIMEZONE).date()
    is_same_day = reminder_type == "same_day"
    reminder_date = today if is_same_day else today + timedelta(days=1)
    sent_count = 0

    logger.info(
        "Scheduler: verificando lembretes de consultas para %s.",
        reminder_date.strftime("%d/%m/%Y"),
    )

    async with AsyncSession() as db:
        clients_result = await db.execute(
            select(ClientWeb)
            .options(selectinload(ClientWeb.slot))
            .where(ClientWeb.status == "confirmed")
        )

        for client in clients_result.scalars().all():
            schedule = _get_client_schedule(client)
            if not schedule:
                continue

            appointment_date, appointment_time = schedule
            if appointment_date != reminder_date:
                continue

            existing_result = await db.execute(
                select(AppointmentReminderLogWeb.id).where(
                    and_(
                        AppointmentReminderLogWeb.client_id == client.id,
                        AppointmentReminderLogWeb.appointment_date == appointment_date,
                        AppointmentReminderLogWeb.appointment_time == appointment_time,
                        AppointmentReminderLogWeb.reminder_type == reminder_type,
                    )
                )
            )
            if existing_result.scalar_one_or_none() is not None:
                continue

            additional_service = ""
            if client.upsell_success and client.upsell_service:
                additional_service = (
                    f"\n➕ *Serviço adicional:* {client.upsell_service}"
                )

            reminder_intro = (
                "Sua consulta na Clínica Lúmina é hoje"
                if is_same_day
                else "Passando para lembrar que sua consulta na Clínica Lúmina é amanhã"
            )
            message = (
                f"Olá, *{client.name}*! 😊\n\n"
                f"{reminder_intro}:\n\n"
                f"🦷 *Procedimento:* {client.service}"
                f"{additional_service}\n"
                f"📅 *Data:* {appointment_date.strftime('%d/%m/%Y')}\n"
                f"🕐 *Horário:* {appointment_time}\n\n"
                "Caso precise remarcar, fale conosco por aqui. "
                "Estamos aguardando você! 🦷✨"
            )

            success = await whatsapp.send_message(client.phone, message)
            if not success:
                logger.warning(
                    "Falha ao enviar lembrete de consulta para %s***.",
                    client.phone[:6],
                )
                continue

            db.add(
                AppointmentReminderLogWeb(
                    client_id=client.id,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    reminder_type=reminder_type,
                )
            )
            await db.commit()
            sent_count += 1

    logger.info(
        "Scheduler: lembretes concluidos. %s mensagem(ns) enviada(s).",
        sent_count,
    )


async def run_appointment_reminder_check():
    """Envia o lembrete na vespera da consulta."""
    await _run_appointment_reminder_check("day_before")


async def run_same_day_appointment_reminder_check():
    """Envia o lembrete na manha da consulta."""
    await _run_appointment_reminder_check("same_day")


def create_scheduler() -> AsyncIOScheduler:
    """Cria e configura o scheduler. Chame start() após criar."""
    scheduler = AsyncIOScheduler(timezone=CLINIC_TIMEZONE)
    scheduler.add_job(
        run_followup_check,
        trigger=CronTrigger(hour=9, minute=0),   # Todo dia às 09:00
        id="followup_daily",
        name="Follow-Up Diário",
        replace_existing=True,
        misfire_grace_time=3600,                 # Tolera até 1h de atraso no boot
    )
    logger.info("📅 Scheduler de follow-up configurado: todo dia às 09:00.")
    scheduler.add_job(
        run_appointment_reminder_check,
        trigger=CronTrigger(hour=9, minute=5, timezone=CLINIC_TIMEZONE),
        id="appointment_reminder_daily",
        name="Lembrete Diario de Consultas",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Scheduler de lembretes configurado: todo dia as 09:05.")
    scheduler.add_job(
        run_same_day_appointment_reminder_check,
        trigger=CronTrigger(hour=7, minute=0, timezone=CLINIC_TIMEZONE),
        id="same_day_appointment_reminder_daily",
        name="Lembrete de Consultas do Mesmo Dia",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Scheduler de lembretes do mesmo dia configurado: 07:00.")
    return scheduler
