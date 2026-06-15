from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from backend.agent.services import session as sess
from backend.agent.services import ai_service, faq_service, whatsapp
from backend.agent.services import schedule_service
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb, ExamWeb, ScheduleSlotWeb
import os
import asyncio
import unicodedata
import re
from datetime import date

router = APIRouter(prefix="/webhook")

INITIAL_GREETING = (
    "Olá! 👋✨\n"
    "Seja bem-vindo(a) à Lumina Clínica Odontológica 🦷✨\n\n"
    "Será um prazer cuidar do seu sorriso!\n\n"
    "Como podemos te ajudar hoje?"
)

SERVICES_PDF_INTRO = "Vou te enviar nossa tabela com os procedimentos que realizamos e seus respectivos valores. 📋✨"

LOCATION_MESSAGE = (
    "📍 Segue a localização da nossa clínica:\n\n"
    "https://maps.app.goo.gl/fqcbXNXctnfnT7Rn6?g_st=ic\n\n"
    "Será um prazer receber você! 🦷✨"
)

SERVICES_PDF_KEYWORDS = [
    "valor", "valores", "preço", "precos", "preço", "preços", "quanto custa",
    "custa quanto", "orçamento", "orcamento", "tabela", "procedimento",
    "procedimentos", "serviço", "servicos", "serviço", "serviços", "exame",
    "exames", "catálogo", "catalogo", "pdf"
]

LOCATION_KEYWORDS = [
    "endereço", "endereco", "localização", "localizacao", "localizaçao",
    "onde fica", "mapa", "maps", "rota", "chegar", "como chegar",
    "local", "fica onde"
]

APPOINTMENT_INTENT_KEYWORDS = [
    "consulta", "consultar", "agendar", "agendamento", "marcar", "horario",
    "horário", "atendimento", "avaliacao", "avaliação"
]

GENERIC_SERVICE_NAMES = {
    "consulta", "consulta odontologica", "consulta odontológica", "avaliacao",
    "avaliação", "atendimento", "atendimento humano", "em andamento",
    "em andamento...", "procedimento", "servico", "serviço", "exame",
    "aguardando procedimento"
}

SERVICE_MATCH_STOPWORDS = {
    "consulta", "consultar", "agendamento", "agendar", "atendimento",
    "avaliacao", "avaliacao", "procedimento", "procedimentos", "servico",
    "servicos", "exame", "exames", "gostaria", "queria", "quero", "marcar"
}

ACKNOWLEDGEMENT_WORDS = {
    "ok", "okay", "certo", "beleza", "blz", "ta", "tá", "sim", "pode",
    "entendi", "combinado", "perfeito"
}

CONFIRMATION_WORDS = {
    "sim", "pode", "confirmar", "confirmo", "quero", "isso", "esse",
    "essa", "ok", "certo", "fechado", "perfeito"
}

REJECTION_WORDS = {"nao", "não", "outro", "trocar", "mudar", "prefiro"}


def _contains_any(text_lower: str, keywords: list[str]) -> bool:
    return any(keyword in text_lower for keyword in keywords)


def _wants_services_pdf(text: str) -> bool:
    return _contains_any(text.lower(), SERVICES_PDF_KEYWORDS)


def _wants_location(text: str) -> bool:
    return _contains_any(text.lower(), LOCATION_KEYWORDS)


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


def _is_acknowledgement(text: str) -> bool:
    normalized = _normalize_label(text)
    return normalized in {_normalize_label(item) for item in ACKNOWLEDGEMENT_WORDS}


def _is_confirmation_text(text: str) -> bool:
    normalized = _normalize_label(text)
    words = set(normalized.split())
    return bool(words & {_normalize_label(item) for item in CONFIRMATION_WORDS})


def _is_rejection_text(text: str) -> bool:
    normalized = _normalize_label(text)
    words = set(normalized.split())
    return bool(words & {_normalize_label(item) for item in REJECTION_WORDS})


def _strip_premature_upsell(text: str) -> str:
    if not text:
        return text
    parts = re.split(r"\n?\s*(?:al[eé]m disso|aproveitando)[,\s]+", text, flags=re.IGNORECASE, maxsplit=1)
    return parts[0].rstrip() if parts else text


def _has_real_service(session: dict) -> bool:
    return bool(session.get("service")) and not _is_generic_service(session.get("service"))


def _wants_appointment_without_service(text: str, session: dict) -> bool:
    text_lower = text.lower()
    if _has_real_service(session):
        return False
    return _contains_any(text_lower, APPOINTMENT_INTENT_KEYWORDS)


async def _ask_for_service_before_scheduling(phone: str, reply_jid: str, session: dict) -> dict:
    session["service"] = None
    session["appointment_date"] = None
    session["slot_date"] = None
    session["slot_time"] = None
    session["awaiting_service"] = True
    if not session.get("services_pdf_sent"):
        session = await _send_services_pdf(phone, reply_jid, session)
    message = (
        "Antes de marcar o horário, preciso saber qual procedimento você deseja realizar. "
        "Pode escolher um da tabela ou escrever outro procedimento, se não estiver na lista. 😊"
    )
    await whatsapp.send_message(phone, message, reply_jid=reply_jid)
    return await sess.add_to_history(session, "assistant", message)


def _valid_cpf(value: str | None) -> bool:
    if not value:
        return False
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return len(digits) >= 11 and digits != "00000000000"


def _client_lookup_filter(phone: str, cpf: str | None = None):
    filters = [ClientWeb.phone == phone]
    if _valid_cpf(cpf):
        filters.append(ClientWeb.cpf == str(cpf)[:14])
    return or_(*filters)


def _service_matches_text(text: str, service_name: str) -> bool:
    text_norm = _normalize_label(text)
    service_norm = _normalize_label(service_name)
    if not text_norm or not service_norm:
        return False
    if text_norm not in SERVICE_MATCH_STOPWORDS and (text_norm in service_norm or service_norm in text_norm):
        return True
    stopwords = {_normalize_label(item) for item in SERVICE_MATCH_STOPWORDS}
    text_words = {word for word in text_norm.replace("(", " ").replace(")", " ").split() if len(word) >= 5 and word not in stopwords}
    service_words = {word for word in service_norm.replace("(", " ").replace(")", " ").split() if len(word) >= 5 and word not in stopwords}
    return bool(text_words & service_words)


async def _detect_service_from_text(text: str, allow_custom: bool = False) -> tuple[str | None, int | None]:
    if _is_generic_service(text):
        return None, None

    async with AsyncSession() as db:
        result = await db.execute(select(ExamWeb))
        exams = result.scalars().all()

    for exam in exams:
        if _service_matches_text(text, exam.name):
            return exam.name, exam.id

    text_norm = _normalize_label(text)
    custom_prefixes = ("outro", "outros", "nao esta na lista", "não está na lista", "nao tem na lista", "não tem na lista")
    if allow_custom and text_norm and not _is_acknowledgement(text) and text_norm.startswith(custom_prefixes) and not schedule_service.parse_appointment_text(text)[0]:
        custom = str(text).replace(":", " ", 1).strip()
        return custom.title(), None
    return None, None


async def _send_services_pdf(phone: str, reply_jid: str, session: dict) -> dict:
    await whatsapp.send_message(phone, SERVICES_PDF_INTRO, reply_jid=reply_jid)
    session = await sess.add_to_history(session, "assistant", SERVICES_PDF_INTRO)

    pdf_path = os.path.join("backend", "agent", "docs", settings.SERVICES_PDF_FILENAME)
    if not os.path.exists(pdf_path):
        logger.warning(f"PDF de serviços não encontrado em {pdf_path}")
        return session

    base_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    if "localhost" in base_url and "baileys:3000" in settings.WHATSAPP_API_URL:
        base_url = "http://backend:8000"

    pdf_url = f"{base_url}/docs-files/{settings.SERVICES_PDF_FILENAME}"
    logger.info(f"Enviando PDF de serviços para {phone[:6]}*** via {pdf_url}")
    await whatsapp.send_document(
        phone=phone,
        pdf_url=pdf_url,
        filename=settings.SERVICES_PDF_FILENAME,
        caption="",
        reply_jid=reply_jid
    )
    session["services_pdf_sent"] = True
    return await sess.add_to_history(
        session,
        "assistant",
        f"[📎 Documento Anexado: {settings.SERVICES_PDF_FILENAME}]\n{SERVICES_PDF_INTRO}"
    )


def _format_client_appointment(client: ClientWeb) -> str:
    if client.slot_date and client.slot:
        return f"{client.slot_date.strftime('%d/%m/%Y')} às {client.slot.time_str}"
    return client.appointment_date or "sem horário definido"


async def _available_slots_message(days_ahead: int = 14) -> str:
    slots = await schedule_service.get_available_slots(days_ahead=days_ahead)
    if not slots:
        return "No momento não encontrei horários livres nos próximos dias. Vou pedir para a recepção conferir uma opção para você. 😊"
    preview = slots[:8]
    lines = ["Tenho estes horários disponíveis:"]
    for slot in preview:
        lines.append(f"• {slot['day_name']} {slot['date_str']} às {slot['time_str']}")
    lines.append("Pode me responder com uma dessas opções, por exemplo: 15/06 às 10:00.")
    return "\n".join(lines)


def _appointment_confirmation_message(session: dict) -> str:
    service = session.get("service") or "procedimento escolhido"
    slot_date = date.fromisoformat(str(session["slot_date"]))
    slot_time = session["slot_time"]
    return (
        "Perfeito! Antes de enviar para a recepção, confirme por favor:\n\n"
        f"🦷 Procedimento: {service}\n"
        f"📅 Data/Hora: {slot_date.strftime('%d/%m/%Y')} às {slot_time}\n\n"
        "Posso enviar essa solicitação de agendamento para a equipe confirmar?"
    )


async def _handle_requested_slot(phone: str, text: str, session: dict, reply_jid: str) -> bool:
    if not (session.get("name") and session.get("cpf") and _has_real_service(session)):
        return False

    requested_date, requested_time = schedule_service.parse_appointment_text(text)
    if requested_time and not requested_date:
        base_date = session.get("pending_slot_date") or session.get("slot_date")
        if not base_date and session.get("appointment_date"):
            parsed_existing_date, _ = schedule_service.parse_appointment_text(session.get("appointment_date"))
            if parsed_existing_date:
                base_date = parsed_existing_date.isoformat()
        if base_date:
            requested_date = date.fromisoformat(str(base_date))

    if not (requested_date and requested_time):
        return False

    slot = await schedule_service.find_slot_by_date_time(requested_date.isoformat(), requested_time)
    if not slot:
        session["appointment_date"] = None
        session["slot_date"] = None
        session["slot_time"] = None
        session["pending_slot_date"] = requested_date.isoformat()
        session["awaiting_slot_confirmation"] = False
        message = (
            f"Esse horário ({requested_date.strftime('%d/%m/%Y')} às {requested_time}) não está disponível na agenda.\n\n"
            f"{await _available_slots_message()}"
        )
        await whatsapp.send_message(phone, message, reply_jid=reply_jid)
        session = await sess.add_to_history(session, "user", text)
        session = await sess.add_to_history(session, "assistant", message)
        await sess.save_session(phone, session)
        return True

    session["appointment_date"] = f"{requested_date.strftime('%d/%m/%Y')} às {requested_time}"
    session["slot_date"] = requested_date.isoformat()
    session["slot_time"] = requested_time
    session["pending_slot_date"] = requested_date.isoformat()
    session["awaiting_slot_confirmation"] = True
    session["confirmed_service"] = session["service"]
    if session.get("exam_id"):
        session["confirmed_exam_id"] = session["exam_id"]
    message = _appointment_confirmation_message(session)
    await whatsapp.send_message(phone, message, reply_jid=reply_jid)
    session = await sess.add_to_history(session, "user", text)
    session = await sess.add_to_history(session, "assistant", message)
    await sess.save_session(phone, session)
    return True


async def _slot_has_capacity(db: AsyncSession, slot_id: int, slot_date: date, current_client_id: int | None = None) -> bool:
    slot_res = await db.execute(select(ScheduleSlotWeb).where(ScheduleSlotWeb.id == slot_id))
    slot = slot_res.scalars().first()
    if not slot or not slot.is_active:
        return False
    count_query = select(func.count(ClientWeb.id)).where(
        ClientWeb.slot_id == slot_id,
        ClientWeb.slot_date == slot_date,
        ClientWeb.status.in_(["pending", "confirmed"])
    )
    if current_client_id:
        count_query = count_query.where(ClientWeb.id != current_client_id)
    booked_res = await db.execute(count_query)
    return (booked_res.scalar() or 0) < slot.max_patients


async def _handle_appointment_self_service(phone: str, text: str, session: dict, phone_for_reply: str) -> bool:
    text_lower = text.lower().strip()
    lookup_keywords = ["histórico", "historico", "minha marcação", "minha marcacao", "meu agendamento", "minha consulta", "verificar acesso", "ver minha agenda", "meu horário", "meu horario"]
    reschedule_keywords = ["remarcar", "mudar horário", "mudar horario", "trocar horário", "trocar horario", "alterar horário", "alterar horario", "mudar minha consulta", "trocar minha consulta"]
    wants_lookup = any(keyword in text_lower for keyword in lookup_keywords)
    wants_reschedule = any(keyword in text_lower for keyword in reschedule_keywords)
    awaiting_reschedule = bool(session.get("awaiting_reschedule"))

    parsed_date, parsed_time = schedule_service.parse_appointment_text(text)
    if not (wants_lookup or wants_reschedule or awaiting_reschedule):
        return False

    async with AsyncSession() as db:
        result = await db.execute(
            select(ClientWeb)
            .options(selectinload(ClientWeb.slot))
            .where(ClientWeb.phone == phone)
            .order_by(ClientWeb.id.desc())
        )
        client = result.scalars().first()

        if not client:
            message = (
                "Ainda não encontrei um agendamento vinculado ao seu WhatsApp. "
                "Me envie seu nome completo, CPF e o serviço desejado para eu iniciar seu cadastro. 😊"
            )
            await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
            return True

        if (wants_reschedule or awaiting_reschedule) and parsed_date and parsed_time:
            slot = await schedule_service.find_slot_by_date_time(parsed_date.isoformat(), parsed_time)
            if not slot:
                message = (
                    f"Encontrei a data {parsed_date.strftime('%d/%m/%Y')} às {parsed_time}, "
                    "mas esse horário não está cadastrado na agenda da clínica.\n\n"
                    f"{await _available_slots_message()}"
                )
                session["awaiting_reschedule"] = True
                await sess.save_session(phone, session)
                await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
                return True

            if not await _slot_has_capacity(db, slot.id, parsed_date, client.id):
                message = (
                    f"Esse horário ({parsed_date.strftime('%d/%m/%Y')} às {parsed_time}) já está preenchido.\n\n"
                    f"{await _available_slots_message()}"
                )
                session["awaiting_reschedule"] = True
                await sess.save_session(phone, session)
                await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
                return True

            client.slot_id = slot.id
            client.slot_date = parsed_date
            client.appointment_date = f"{parsed_date.strftime('%d/%m/%Y')} às {parsed_time}"
            client.status = "pending"
            client.needs_human = False
            await db.commit()

            session["appointment_date"] = client.appointment_date
            session["slot_date"] = parsed_date.isoformat()
            session["slot_time"] = parsed_time
            session["awaiting_reschedule"] = False
            await sess.save_session(phone, session)

            message = (
                f"Perfeito! Atualizei sua solicitação para {client.appointment_date}. "
                "Ela voltou para a recepção aprovar e te confirmar por aqui. 😊"
            )
            await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
            return True

        appointment = _format_client_appointment(client)
        status_map = {
            "pending": "pendente de aprovação",
            "confirmed": "confirmado",
            "cancelled": "recusado/cancelado",
        }
        status_text = status_map.get(client.status, client.status or "pendente")
        message = (
            f"Encontrei seu agendamento de {client.service}: {appointment}.\n"
            f"Status: {status_text}."
        )
        if wants_reschedule:
            session["awaiting_reschedule"] = True
            await sess.save_session(phone, session)
            message += f"\n\n{await _available_slots_message()}"
        else:
            message += "\n\nSe quiser remarcar, me diga: quero mudar horário."

        await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
        return True


@router.post("/message")
async def receive_message(request: Request, bg: BackgroundTasks):
    body = await request.json()
    phone = body.get("phone", "")
    phone_for_reply = body.get("phone_for_reply", "") or phone  # JID completo para resposta (@lid ou @s.whatsapp.net)
    text = body.get("message", "").strip()
    push_name = body.get("push_name", "")

    media = body.get("media", None)

    if not phone or (not text and not media):
        return {"status": "ignored"}

    bg.add_task(handle, phone, text, push_name, phone_for_reply, media)
    return {"status": "ok"}


async def handle(phone: str, text: str, push_name: str = "", phone_for_reply: str = None, media: dict = None):
    # phone_for_reply: JID completo para enviar respostas (pode ser @lid ou @s.whatsapp.net)
    # phone: número limpo sem sufixo, usado como chave de sessão e no banco de dados
    if not phone_for_reply:
        phone_for_reply = phone
    logger.info(f"Mensagem de {phone[:6]}*** | reply_jid={phone_for_reply} | media={'sim' if media else 'nao'} | '{text[:50]}'")
    session = await sess.get_session(phone)
    if push_name and not session.get("name"):
        session["name"] = push_name
    # Salva o JID de resposta na sessão para envios futuros
    session["phone_for_reply"] = phone_for_reply

    # 0. Processamento inicial de mídia (Áudio)
    if media and media["type"] == "audio":
        try:
            transcribed_text = await ai_service.transcribe_audio(media["data"], media["mimetype"])
            if transcribed_text:
                text = f"[Áudio Transcrito do Paciente]: {transcribed_text}"
            else:
                text = "[Paciente enviou um áudio vazio ou ininteligível.]"
        except Exception as e:
            logger.error(f"Erro na transcrição de áudio: {e}")
            text = "[Paciente enviou um arquivo de áudio que eu não consigo ler. Peça educadamente para ele escrever em texto.]"
        media = None # Após transcrever, tratamos como texto normal
    
    if not text and media and media["type"] == "image":
        text = "[Paciente enviou uma imagem]"

    # 1. Verifica PRIORIDADE MÁXIMA: Gatilho de suporte humano por palavras-chave
    keywords_human = ["humano", "atendente", "recepcionista", "falar com alguem", "falar com alguém", "pessoa", "suporte", "falar com um", "atendimento humano"]
    text_lower = text.lower().strip()
    user_requested_human = any(kw in text_lower for kw in keywords_human)

    # 2. Verifica se o usuário quer reiniciar a conversa (secundário ao suporte humano)
    RESET_KEYWORDS = ["recomeça", "recomeca", "reiniciar", "reinicia", "zera", "zerar", "começa de novo", "comeca de novo", "restart", "reset", "reseta", "resetar", "novo atendimento", "começar de novo", "apaga tudo", "esquece tudo", "ignora tudo", "apagar histórico", "limpar conversa"]
    is_reset = not user_requested_human and any(kw in text_lower for kw in RESET_KEYWORDS)

    if is_reset:
        await sess.delete_session(phone)
        new_session = {
            "phone": phone,
            "history": [],
            "ai_attempts": 0,
            "escalated": False,
            "name": push_name or None,
            "cpf": None,
            "service": None,
            "appointment_date": None,
            "upsell_success": False,
            "upsell_service": None,
            "source": "whatsapp",
            "phone_for_reply": phone_for_reply,
        }
        await sess.save_session(phone, new_session)
        await whatsapp.send_message(phone, INITIAL_GREETING, reply_jid=phone_for_reply)
        new_session = await sess.add_to_history(new_session, "assistant", INITIAL_GREETING)
        await sess.save_session(phone, new_session)
        logger.info(f"Sessão reiniciada por comando do usuário: {phone[:6]}***")

        async with AsyncSession() as db:
            try:
                stmt = (
                    select(ClientWeb)
                    .where(_client_lookup_filter(phone, session.get("cpf")))
                    .order_by(ClientWeb.id.desc())
                )
                result = await db.execute(stmt)
                client_record = result.scalars().first()
                if client_record and client_record.status == "pending" and (not client_record.service or client_record.service == "Atendimento Humano"):
                    await db.delete(client_record)
                    await db.commit()
                    logger.info(f"Cliente {phone} removido do painel (zera/reiniciar).")
            except Exception as e:
                logger.error(f"Erro ao remover cliente do painel no reset: {e}")

        return

    if session.get("escalated"):
        async with AsyncSession() as db:
            result = await db.execute(select(ClientWeb).where(ClientWeb.phone == phone))
            client_record = result.scalars().first()
            if not client_record or not client_record.needs_human:
                logger.info(f"Sessão escalada antiga liberada para IA: {phone[:6]}***")
                session["escalated"] = False
                session["needs_human"] = False
                session["ai_attempts"] = 0
                await sess.save_session(phone, session)

    if session["escalated"]:
        # Se o usuário manda mensagem com reset enquanto escalado, deixa o reset funcionar normalmente (já tratado acima).
        # Caso contrário, só ignora silenciosamente para não responder como IA enquanto atendente humano está em jogo.
        # Mas re-checa se o painel já desativou o 'escalated' (começa fresco)
        logger.info(f"Sessão escalada para humano detectada: {phone[:6]}***. Ignorando IA.")
        return

    # Determinar se é a primeira mensagem do paciente antes de atualizar o histórico
    is_first_message = len(session.get("history", [])) == 0

    # Censura CPF na entrada para a IA/Histórico, mas captura o CPF completo para o banco de dados
    censored_text, detected_cpf = ai_service.extract_and_censor_cpf(text)
    if detected_cpf:
        logger.info(f"CPF detectado e censurado para a IA: {detected_cpf[:5]}******")
        session["cpf"] = detected_cpf[:14]

    # Detecta se veio do Instagram pela mensagem inicial (Deep link do ManyChat)
    lower_text = text.lower()
    if "instagram" in lower_text or "insta" in lower_text:
        logger.info(f"Origem do cliente detectada como INSTAGRAM via mensagem inicial!")
        session["source"] = "instagram"

    skip_ai_response = False
    if session.get("awaiting_slot_confirmation"):
        if _is_rejection_text(text):
            session["appointment_date"] = None
            session["slot_date"] = None
            session["slot_time"] = None
            session["awaiting_slot_confirmation"] = False
            message = "Sem problemas. Me diga outro dia e horário que você prefere para eu verificar na agenda. 😊"
            await whatsapp.send_message(phone, message, reply_jid=phone_for_reply)
            session = await sess.add_to_history(session, "user", censored_text)
            session = await sess.add_to_history(session, "assistant", message)
            await sess.save_session(phone, session)
            return
        if _is_confirmation_text(text):
            session["awaiting_slot_confirmation"] = False
            if session.get("confirmed_service"):
                session["service"] = session["confirmed_service"]
            if session.get("confirmed_exam_id"):
                session["exam_id"] = session["confirmed_exam_id"]
            skip_ai_response = True

    if await _handle_appointment_self_service(phone, text, session, phone_for_reply):
        return

    if _wants_location(text):
        await whatsapp.send_message(phone, LOCATION_MESSAGE, reply_jid=phone_for_reply)
        session = await sess.add_to_history(session, "user", censored_text)
        session = await sess.add_to_history(session, "assistant", LOCATION_MESSAGE)
        await sess.save_session(phone, session)
        return

    if _wants_services_pdf(text):
        session = await sess.add_to_history(session, "user", censored_text)
        session = await _send_services_pdf(phone, phone_for_reply, session)
        await sess.save_session(phone, session)
        return

    detected_service, detected_exam_id = await _detect_service_from_text(
        text,
        allow_custom=bool(session.get("awaiting_service"))
    )
    if detected_service:
        session["service"] = detected_service
        session["awaiting_service"] = False
        if detected_exam_id:
            session["exam_id"] = detected_exam_id
    elif session.get("awaiting_service"):
        session = await sess.add_to_history(session, "user", censored_text)
        session = await _ask_for_service_before_scheduling(phone, phone_for_reply, session)
        await sess.save_session(phone, session)
        return

    if _wants_appointment_without_service(text, session):
        session = await sess.add_to_history(session, "user", censored_text)
        session = await _ask_for_service_before_scheduling(phone, phone_for_reply, session)
        await sess.save_session(phone, session)
        return

    if await _handle_requested_slot(phone, text, session, phone_for_reply):
        return

    if is_first_message and not user_requested_human:
        await whatsapp.send_message(phone, INITIAL_GREETING, reply_jid=phone_for_reply)
        session = await sess.add_to_history(session, "user", censored_text)
        session = await sess.add_to_history(session, "assistant", INITIAL_GREETING)
        await sess.save_session(phone, session)
        return

    # 1. tenta FAQ usando o texto censurado
    answer, score = faq_service.search_faq(censored_text)
    if answer and score >= 0.6:
        await whatsapp.send_message(phone, answer, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "user", censored_text)
        session = await sess.add_to_history(session, "assistant", answer)
        await sess.save_session(phone, session)
        return

    needs_human_trigger = (
        user_requested_human or 
        (session.get("ai_attempts", 0) >= settings.MAX_AI_ATTEMPTS)
    )

    metadata = {}
    confidence = 1.0
    response = ""

    # Se NÃO disparou o gatilho de humano ainda, consulta a IA
    if not needs_human_trigger and not skip_ai_response:
        # 2. consulta IA usando o texto censurado
        context = faq_service.get_context(censored_text)
        try:
            response, confidence, metadata = await ai_service.get_response(censored_text, session["history"], context, media=media)
        except Exception as e:
            logger.error(f"Erro ao consultar IA para {phone[:6]}***: {e}")
            response = (
                "Tive uma instabilidade para consultar as informações agora. "
                "Vou chamar nossa equipe para te ajudar por aqui. 🧡"
            )
            confidence = 1.0
            metadata = {"needs_human": True}
        
        # Atualiza o gatilho caso a IA tenha decidido transferir
        if metadata and metadata.get("needs_human") is True:
            needs_human_trigger = True

        # Se a IA capturou um novo horario, verifica se ha conflito com consultas ja confirmadas
        if metadata and metadata.get("appointment_date"):
            new_date = metadata["appointment_date"]
            if new_date != session.get("appointment_date"):
                async with AsyncSession() as db:
                    try:
                        stmt = select(ClientWeb).where(
                            ClientWeb.appointment_date == new_date,
                            ClientWeb.status == "confirmed"
                        )
                        result = await db.execute(stmt)
                        conflict = result.scalars().first()
                        
                        if conflict:
                            logger.info(f"Conflito de horario detectado para {new_date}. Solicitando novo horario a IA...")
                            temp_history = session["history"] + [
                                {"role": "system", "content": f"O horario '{new_date}' ja esta reservado por outro paciente com consulta confirmada. Avise o cliente educadamente que esse horario ja esta ocupado e peca para ele sugerir outro dia ou horario."}
                            ]
                            response, confidence, metadata = await ai_service.get_response(censored_text, temp_history, context)
                            if metadata:
                                metadata["appointment_date"] = None
                    except Exception as e:
                        logger.error(f"Erro ao verificar conflito de horario: {e}")

        if confidence < settings.AI_CONFIDENCE_THRESHOLD:
            session["ai_attempts"] += 1
        else:
            session["ai_attempts"] = 0

    # Atualiza dados da sessão caso a IA tenha capturado novos metadados
    if metadata:
        for key in ["name", "cpf", "service", "appointment_date", "slot_date", "slot_time", "upsell_success", "upsell_service", "needs_human"]:
            if metadata.get(key) is not None and metadata.get(key) != "" and metadata.get(key) != "null":
                if key == "cpf":
                    # Se já temos um CPF válido (>= 11 chars e sem asteriscos), não deixa a IA sobrescrever com alucinação
                    if session.get("cpf") and len(str(session["cpf"])) >= 11 and "*" not in str(session["cpf"]):
                        continue
                    if "*" in str(metadata[key]):
                        continue
                    session[key] = str(metadata[key])[:14]
                elif key == "service":
                    if session.get("confirmed_service"):
                        continue
                    if _is_generic_service(metadata[key]):
                        continue
                    session[key] = metadata[key]
                    session["awaiting_service"] = False
                else:
                    session[key] = metadata[key]

    if _is_generic_service(session.get("service")):
        session["service"] = None

    direct_date, direct_time = schedule_service.parse_appointment_text(text)
    if direct_date and direct_time and not session.get("appointment_date"):
        session["appointment_date"] = f"{direct_date.strftime('%d/%m/%Y')} às {direct_time}"
        if not _is_confirmation_text(text):
            session["awaiting_slot_confirmation"] = True

    if session.get("appointment_date") and (not session.get("slot_date") or not session.get("slot_time")):
        if not direct_date or not direct_time:
            direct_date, direct_time = schedule_service.parse_appointment_text(session.get("appointment_date"))
        if direct_date and direct_time:
            session["slot_date"] = direct_date.isoformat()
            session["slot_time"] = direct_time
            session["appointment_date"] = f"{direct_date.strftime('%d/%m/%Y')} às {direct_time}"
            if text.strip() and not _is_confirmation_text(text) and schedule_service.parse_appointment_text(text)[0]:
                session["awaiting_slot_confirmation"] = True

    # Adicionar mensagem do usuário à história da sessão
    session = await sess.add_to_history(session, "user", censored_text)

    if session.get("appointment_date") and not _has_real_service(session):
        session = await _ask_for_service_before_scheduling(phone, phone_for_reply, session)
        await sess.save_session(phone, session)
        return

    if needs_human_trigger:
        await whatsapp.send_escalation(phone, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "assistant", "A sua demanda foi acionada, logo mais uma secretária vai entrar em contato")
        session["escalated"] = True
        
        # Salva ou atualiza ClientWeb no banco de dados com needs_human=True
        async with AsyncSession() as db:
            try:
                stmt = (
                    select(ClientWeb)
                    .where(_client_lookup_filter(phone, session.get("cpf")))
                    .order_by(ClientWeb.id.desc())
                )
                result = await db.execute(stmt)
                client_record = result.scalars().first()
                
                if not client_record:
                    client_record = ClientWeb(
                        name=session.get("name") or f"Paciente ({phone[-4:]})",
                        cpf=str(session.get("cpf"))[:14] if session.get("cpf") else "000.000.000-00",
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service="Atendimento Humano",
                        appointment_date=None,
                        upsell_success=False,
                        upsell_service=None,
                        status="pending",
                        needs_human=True
                    )
                    db.add(client_record)
                else:
                    client_record.needs_human = True
                await db.commit()
                logger.info(f"Cliente {phone} marcado para atendimento humano no banco.")
            except Exception as e:
                logger.error(f"Erro ao salvar necessidade de atendimento humano: {e}")
        
        # Salva a sessão no Redis antes de retornar, para garantir que 'escalated=True' persista
        await sess.save_session(phone, session)
        return
    elif not skip_ai_response:
        # Enviar resposta da IA
        sent_response = response
        if session.get("awaiting_slot_confirmation"):
            sent_response = _strip_premature_upsell(sent_response)
        if confidence < settings.AI_CONFIDENCE_THRESHOLD:
            sent_response += "\n\n_Caso queira falar com um atendente, é só pedir!_"
            
        await whatsapp.send_message(phone, sent_response, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "assistant", sent_response)

        # Audita a resposta em background sem bloquear o usuário
        asyncio.create_task(ai_service.audit_response_in_background(text, sent_response))

    # 3. Registro Automático se os dados essenciais estiverem preenchidos (CPF é opcional)
    has_name = bool(session.get("name"))
    has_service = _has_real_service(session)
    has_date = bool(session.get("appointment_date")) and not session.get("awaiting_slot_confirmation")
    logger.info(f"[REGISTRO] name={session.get('name')!r} service={session.get('service')!r} date={session.get('appointment_date')!r} cpf={'****' if session.get('cpf') else None}")
    if has_name and has_service and has_date:
        async with AsyncSession() as db:
            try:
                stmt = (
                    select(ClientWeb)
                    .where(_client_lookup_filter(phone, session.get("cpf")))
                    .order_by(ClientWeb.id.desc())
                )
                result = await db.execute(stmt)
                existing = result.scalars().first()

                # Resolve exam_id
                exam_id = session.get("confirmed_exam_id") or session.get("exam_id")
                service_name = session.get("confirmed_service") or session["service"]
                if exam_id:
                    exam_res = await db.execute(select(ExamWeb).where(ExamWeb.id == int(exam_id)))
                    exam = exam_res.scalars().first()
                    if exam:
                        service_name = exam.name
                else:
                    exams_res = await db.execute(select(ExamWeb))
                    exams = exams_res.scalars().all()
                    for exam in exams:
                        if _service_matches_text(service_name, exam.name):
                            exam_id = exam.id
                            service_name = exam.name
                            break

                # Resolve slot_id e slot_date a partir dos metadados capturados
                slot_id = None
                slot_date_obj = None
                raw_slot_date = session.get("slot_date")
                raw_slot_time = session.get("slot_time")
                if raw_slot_date and raw_slot_time:
                    try:
                        slot_date_obj = date.fromisoformat(str(raw_slot_date))
                        found_slot = await schedule_service.find_slot_by_date_time(
                            str(raw_slot_date), str(raw_slot_time)
                        )
                        if found_slot:
                            slot_id = found_slot.id
                    except Exception as e:
                        logger.error(f"Erro ao resolver slot: {e}")

                # Checar se o dia é ocupado (2 ou mais horários marcados com este agendamento)
                is_busy_day = False
                if slot_date_obj:
                    query_booked = select(func.count(ClientWeb.id)).where(
                        ClientWeb.slot_date == slot_date_obj,
                        ClientWeb.status.in_(["pending", "confirmed"])
                    )
                    if existing:
                        query_booked = query_booked.where(ClientWeb.id != existing.id)
                    day_booked_res = await db.execute(query_booked)
                    other_booked = day_booked_res.scalar() or 0
                    if other_booked >= 1:
                        is_busy_day = True

                if not existing:
                    logger.info(f"Registrando agendamento de {session['name']}...")
                    new_client = ClientWeb(
                        name=session["name"],
                        cpf=str(session.get("cpf") or "000.000.000-00")[:14],
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service=service_name,
                        appointment_date=session["appointment_date"],
                        slot_id=slot_id,
                        slot_date=slot_date_obj,
                        upsell_success=session.get("upsell_success", False),
                        upsell_service=session.get("upsell_service"),
                        status="pending",
                        exam_id=exam_id,
                        needs_human=is_busy_day
                    )
                    db.add(new_client)
                    await db.commit()
                    logger.info("Agendamento registrado como pendente com sucesso!")
                else:
                    logger.info(f"Atualizando agendamento para {phone}...")
                    existing.name = session["name"]
                    existing.cpf = str(session.get("cpf") or existing.cpf or "000.000.000-00")[:14]
                    existing.phone = phone
                    existing.service = service_name
                    existing.appointment_date = session["appointment_date"]
                    existing.slot_id = slot_id
                    existing.slot_date = slot_date_obj
                    existing.upsell_success = session.get("upsell_success", False)
                    existing.upsell_service = session.get("upsell_service")
                    existing.exam_id = exam_id
                    existing.status = "pending"
                    if is_busy_day:
                        existing.needs_human = True
                    await db.commit()
                    logger.info("Agendamento atualizado e retornado a pendente com sucesso!")

                # Mensagem de confirmação unificada para novos e existentes
                confirm_msg = (
                    f"📅 *Agendamento Solicitado!*\n\n"
                    f"Olá *{session['name']}*, sua consulta de *{service_name}* foi enviada à nossa equipe.\n"
                )
                if slot_date_obj and raw_slot_time:
                    confirm_msg += f"📅 *Data/Hora:* {slot_date_obj.strftime('%d/%m/%Y')} às {raw_slot_time}\n"
                else:
                    confirm_msg += f"📅 *Data/Hora Sugerida:* {session['appointment_date']}\n"
                if session.get("upsell_success") and session.get("upsell_service"):
                    confirm_msg += f"➕ *Serviço Adicional:* {session['upsell_service']}\n"
                
                if is_busy_day:
                    confirm_msg += "\n⚠️ *Nota:* Como este dia está bastante concorrido, nossa atendente foi chamada para confirmar o seu horário. Entraremos em contato em breve! 😊"
                else:
                    confirm_msg += "\nSua consulta será confirmada em até *24 horas*! Te avisaremos aqui. 😊"
                
                await whatsapp.send_message(phone, confirm_msg, reply_jid=session.get("phone_for_reply"))
                session = await sess.add_to_history(session, "assistant", confirm_msg)

                # O dashboard já sinaliza pacientes que precisam de atendimento humano (is_busy_day).
                # Não é necessário enviar notificação via WhatsApp para o próprio número da clínica.
            except Exception as e:
                logger.error(f"Erro ao salvar agendamento automático: {e}")

    # Atualiza incrementalmente o banco de dados com Nome e CPF se o cliente já existir,
    # ou cria um rascunho se tiver nome e CPF mas ainda não terminou o fluxo
    if session.get("name") or session.get("cpf"):
        async with AsyncSession() as db:
            try:
                stmt = (
                    select(ClientWeb)
                    .where(_client_lookup_filter(phone, session.get("cpf")))
                    .order_by(ClientWeb.id.desc())
                )
                result = await db.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    existing.phone = phone
                    if session.get("name"):
                        existing.name = session["name"]
                    if session.get("cpf"):
                        existing.cpf = str(session["cpf"])[:14]
                    if _has_real_service(session):
                        session_exam_id = session.get("confirmed_exam_id") or session.get("exam_id")
                        if session_exam_id:
                            exam_res = await db.execute(select(ExamWeb).where(ExamWeb.id == int(session_exam_id)))
                            exam = exam_res.scalars().first()
                            if exam:
                                existing.service = exam.name
                                existing.exam_id = exam.id
                            else:
                                existing.service = session["service"]
                        else:
                            existing.service = session["service"]
                    await db.commit()
                else:
                    # Se tivermos pelo menos o nome, já criamos um rascunho do paciente no painel
                    if session.get("name"):
                        new_client = ClientWeb(
                            name=session["name"],
                            cpf=str(session.get("cpf") or "000.000.000-00")[:14],
                            phone=phone,
                            source=session.get("source", "whatsapp"),
                            service=session.get("service") if _has_real_service(session) else "Aguardando procedimento",
                            appointment_date=session.get("appointment_date") if _has_real_service(session) and not session.get("awaiting_slot_confirmation") else None,
                            status="pending"
                        )
                        db.add(new_client)
                        await db.commit()
                        logger.info("Criou paciente rascunho no DB incremental.")
            except Exception as e:
                logger.error(f"Erro na atualização incremental do DB: {e}")

    await sess.save_session(phone, session)
