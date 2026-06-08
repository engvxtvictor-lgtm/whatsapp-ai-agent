from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy import select, func
from backend.agent.services import session as sess
from backend.agent.services import ai_service, faq_service, whatsapp
from backend.agent.services import schedule_service
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb, ExamWeb
import os
import asyncio
from datetime import date

router = APIRouter(prefix="/webhook")


@router.post("/message")
async def receive_message(request: Request, bg: BackgroundTasks):
    body = await request.json()
    phone = body.get("phone", "")
    phone_for_reply = body.get("phone_for_reply", "") or phone  # JID completo para resposta (@lid ou @s.whatsapp.net)
    text = body.get("message", "").strip()
    profile_pic = body.get("profile_pic", None)
    push_name = body.get("push_name", "")

    if not phone or not text:
        return {"status": "ignored"}

    bg.add_task(handle, phone, text, profile_pic, push_name, phone_for_reply)
    return {"status": "ok"}


async def handle(phone: str, text: str, profile_pic: str = None, push_name: str = "", phone_for_reply: str = None):
    # phone_for_reply: JID completo para enviar respostas (pode ser @lid ou @s.whatsapp.net)
    # phone: número limpo sem sufixo, usado como chave de sessão e no banco de dados
    if not phone_for_reply:
        phone_for_reply = phone
    logger.info(f"Mensagem de {phone[:6]}*** | reply_jid={phone_for_reply} | '{text[:50]}'")
    session = await sess.get_session(phone)
    if profile_pic:
        session["profile_pic"] = profile_pic
    if push_name and not session.get("name"):
        session["name"] = push_name
    # Salva o JID de resposta na sessão para envios futuros
    session["phone_for_reply"] = phone_for_reply

    # Verifica se o usuário quer reiniciar a conversa
    RESET_KEYWORDS = ["recomeça", "recomeca", "reiniciar", "reinicia", "zera", "zerar", "começa de novo", "comeca de novo", "restart", "reset", "novo atendimento", "começar de novo"]
    text_lower_reset = text.lower().strip()
    is_reset = any(kw in text_lower_reset for kw in RESET_KEYWORDS)

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
            "profile_pic": profile_pic or None,
            "phone_for_reply": phone_for_reply,
        }
        await sess.save_session(phone, new_session)
        reset_msg = "Tudo bem! 😊 Vou começar um novo atendimento para você. Acabei de enviar novamente o nosso catálogo logo abaixo. Qual serviço chamou sua atenção?"
        await whatsapp.send_message(phone, reset_msg, reply_jid=phone_for_reply)
        # Reenvia o PDF
        pdf_path = os.path.join("backend", "agent", "docs", settings.SERVICES_PDF_FILENAME)
        if os.path.exists(pdf_path):
            base_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
            if "localhost" in base_url and "baileys:3000" in settings.WHATSAPP_API_URL:
                base_url = "http://backend:8000"
            pdf_url = f"{base_url}/docs-files/{settings.SERVICES_PDF_FILENAME}"
            await whatsapp.send_document(phone=phone, pdf_url=pdf_url, filename=settings.SERVICES_PDF_FILENAME, caption="📄 Segue nossa tabela completa de serviços e valores!", reply_jid=phone_for_reply)
        logger.info(f"Sessão reiniciada por comando do usuário: {phone[:6]}***")
        return

    if session["escalated"]:
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

    # 1. tenta FAQ usando o texto censurado
    answer, score = faq_service.search_faq(censored_text)
    if answer and score >= 0.6:
        await whatsapp.send_message(phone, answer, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "user", censored_text)
        session = await sess.add_to_history(session, "assistant", answer)
        await sess.save_session(phone, session)
        return

    # 2. consulta IA usando o texto censurado
    context = faq_service.get_context(censored_text)
    response, confidence, metadata = await ai_service.get_response(censored_text, session["history"], context)
    
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
                    if "*" in str(metadata[key]):
                        continue
                    session[key] = str(metadata[key])[:14]
                else:
                    session[key] = metadata[key]

    # Verifica gatilho de suporte humano por palavras-chave na mensagem do usuario
    keywords = ["humano", "atendente", "recepcionista", "falar com alguem", "falar com alguém", "pessoa", "suporte", "falar com um", "atendimento humano"]
    text_lower = text.lower()
    user_requested_human = any(kw in text_lower for kw in keywords)

    needs_human_trigger = (
        user_requested_human or 
        (metadata and metadata.get("needs_human") is True) or
        (session["ai_attempts"] >= settings.MAX_AI_ATTEMPTS)
    )

    # Adicionar mensagem do usuário à história da sessão
    session = await sess.add_to_history(session, "user", censored_text)

    if needs_human_trigger:
        await whatsapp.send_escalation(phone, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "assistant", "Vou te transferir para um atendente agora. Aguarde um momento! 🙏")
        await whatsapp.notify_agent(phone, censored_text, session.get("history", []))
        session["escalated"] = True
        
        # Salva ou atualiza ClientWeb no banco de dados com needs_human=True
        async with AsyncSession() as db:
            try:
                stmt = select(ClientWeb).where(ClientWeb.phone == phone)
                result = await db.execute(stmt)
                client_record = result.scalars().first()
                
                if not client_record:
                    client_record = ClientWeb(
                        name=session.get("name") or f"Paciente ({phone[-4:]})",
                        cpf=str(session.get("cpf"))[:14] if session.get("cpf") else "000.000.000-00",
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service="Atendimento Humano",
                        profile_pic=session.get("profile_pic") or f"https://api.dicebear.com/7.x/adventurer/svg?seed={phone}",
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
    else:
        # Enviar resposta da IA
        sent_response = response
        if confidence < settings.AI_CONFIDENCE_THRESHOLD:
            sent_response += "\n\n_Caso queira falar com um atendente, é só pedir!_"
            
        await whatsapp.send_message(phone, sent_response, reply_jid=session.get("phone_for_reply"))
        session = await sess.add_to_history(session, "assistant", sent_response)

        # Audita a resposta em background sem bloquear o usuário
        asyncio.create_task(ai_service.audit_response_in_background(text, sent_response))

        # Envia o PDF de serviços na primeira mensagem do paciente
        pdf_path = os.path.join("backend", "agent", "docs", settings.SERVICES_PDF_FILENAME)
        if is_first_message and os.path.exists(pdf_path):
            # Resolve o problema do docker-compose injetar localhost
            base_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
            if "localhost" in base_url and "baileys:3000" in settings.WHATSAPP_API_URL:
                base_url = "http://backend:8000"
                
            pdf_url = f"{base_url}/docs-files/{settings.SERVICES_PDF_FILENAME}"
            logger.info(f"Enviando PDF de serviços para {phone[:6]}*** via {pdf_url}")
            await whatsapp.send_document(
                phone=phone,
                pdf_url=pdf_url,
                filename=settings.SERVICES_PDF_FILENAME,
                caption="📄 Segue nossa tabela completa de serviços e valores!",
                reply_jid=session.get("phone_for_reply")
            )
            session = await sess.add_to_history(
                session, 
                "assistant", 
                f"[📎 Documento Anexado: {settings.SERVICES_PDF_FILENAME}]\n📄 Segue nossa tabela completa de serviços e valores!"
            )

    # 3. Registro Automático se os dados essenciais estiverem preenchidos (CPF é opcional)
    has_name = bool(session.get("name"))
    has_service = bool(session.get("service"))
    has_date = bool(session.get("appointment_date"))
    logger.info(f"[REGISTRO] name={session.get('name')!r} service={session.get('service')!r} date={session.get('appointment_date')!r} cpf={'****' if session.get('cpf') else None}")
    if has_name and has_service and has_date:
        async with AsyncSession() as db:
            try:
                stmt = select(ClientWeb).where(ClientWeb.phone == phone)
                result = await db.execute(stmt)
                existing = result.scalars().first()

                # Resolve exam_id
                exam_id = None
                service_name = session["service"]
                exams_res = await db.execute(select(ExamWeb))
                exams = exams_res.scalars().all()
                for exam in exams:
                    if (service_name.lower() in exam.name.lower()) or (exam.name.lower() in service_name.lower()):
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
                        profile_pic=session.get("profile_pic") or f"https://api.dicebear.com/7.x/adventurer/svg?seed={session.get('name', phone)}",
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
                    existing.service = service_name
                    existing.profile_pic = session.get("profile_pic") or existing.profile_pic
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
                
                await whatsapp.send_message(phone, confirm_msg)
                session = await sess.add_to_history(session, "assistant", confirm_msg)

                # Notifica a recepção se o dia estiver ocupado
                if is_busy_day:
                    time_display = raw_slot_time if raw_slot_time else session['appointment_date']
                    await whatsapp.notify_agent(phone, f"Dia ocupado! Confirmar horário de {session['name']} para {time_display}", session.get("history", []))
            except Exception as e:
                logger.error(f"Erro ao salvar agendamento automático: {e}")

    await sess.save_session(phone, session)
