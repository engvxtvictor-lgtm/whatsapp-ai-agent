"""
Scheduler de Follow-Up Automático da Clínica Lúmina.

Roda todo dia às 09:00 (horário local) e verifica se algum cliente
confirmado atingiu o prazo de um follow-up ativo. Se sim, dispara
a mensagem no WhatsApp automaticamente.
"""
import re
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb, FollowupWeb, FollowupLogWeb
from backend.agent.services import whatsapp
from backend.system.logger import logger


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

                # Calcula a data alvo para o follow-up
                target_date = appointment_date + timedelta(days=followup.delay_days)

                # Só dispara se hoje é o dia certo (ou passou — envia com até 3 dias de atraso)
                days_overdue = (today - target_date).days
                if not (0 <= days_overdue <= 3):
                    continue

                # Verifica se já foi enviado para esse cliente+followup
                log_res = await db.execute(
                    select(FollowupLogWeb).where(
                        and_(
                            FollowupLogWeb.client_id == client.id,
                            FollowupLogWeb.followup_id == followup.id,
                        )
                    )
                )
                already_sent = log_res.scalars().first()
                if already_sent:
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


def create_scheduler() -> AsyncIOScheduler:
    """Cria e configura o scheduler. Chame start() após criar."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_followup_check,
        trigger=CronTrigger(hour=9, minute=0),   # Todo dia às 09:00
        id="followup_daily",
        name="Follow-Up Diário",
        replace_existing=True,
        misfire_grace_time=3600,                 # Tolera até 1h de atraso no boot
    )
    logger.info("📅 Scheduler de follow-up configurado: todo dia às 09:00.")
    return scheduler
