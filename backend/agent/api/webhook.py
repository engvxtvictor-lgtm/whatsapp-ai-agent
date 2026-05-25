from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy import select
from backend.agent.services import session as sess
from backend.agent.services import ai_service, faq_service, whatsapp
from backend.agent.services import schedule_service
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb, ExamWeb
import os
from datetime import date

router = APIRouter(prefix="/webhook")


@router.post("/message")
async def receive_message(request: Request, bg: BackgroundTasks):
    body = await request.json()
    phone = body.get("phone", "")
    text = body.get("message", "").strip()

    if not phone or not text:
        return {"status": "ignored"}

    bg.add_task(handle, phone, text)
    return {"status": "ok"}


async def handle(phone: str, text: str):
    logger.info(f"Mensagem de {phone[:6]}*** | '{text[:50]}'")
    session = await sess.get_session(phone)

    if session["escalated"]:
        return

    # Censura CPF na entrada para a IA/Histórico, mas captura o CPF completo para o banco de dados
    censored_text, detected_cpf = ai_service.extract_and_censor_cpf(text)
    if detected_cpf:
        logger.info(f"CPF detectado e censurado para a IA: {detected_cpf[:5]}******")
        session["cpf"] = detected_cpf

    # Detecta se veio do Instagram pela mensagem inicial (Deep link do ManyChat)
    lower_text = text.lower()
    if "instagram" in lower_text or "insta" in lower_text:
        logger.info(f"Origem do cliente detectada como INSTAGRAM via mensagem inicial!")
        session["source"] = "instagram"

    # 1. tenta FAQ usando o texto censurado
    answer, score = faq_service.search_faq(censored_text)
    if answer and score >= 0.6:
        await whatsapp.send_message(phone, answer)
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

    if needs_human_trigger:
        await whatsapp.send_escalation(phone)
        await whatsapp.notify_agent(phone, censored_text)
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
                        cpf=session.get("cpf") or "000.000.000-00",
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service="Atendimento Humano",
                        profile_pic=f"https://api.dicebear.com/7.x/adventurer/svg?seed={phone}",
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
    else:
        if confidence >= settings.AI_CONFIDENCE_THRESHOLD:
            await whatsapp.send_message(phone, response)
        else:
            await whatsapp.send_message(phone,
                response + "\n\n_Caso queira falar com um atendente, é só pedir!_"
            )

        # Envia o PDF de serviços na primeira mensagem do paciente
        is_first_message = len(session.get("history", [])) == 0
        pdf_path = os.path.join("backend", "agent", "docs", settings.SERVICES_PDF_FILENAME)
        if is_first_message and os.path.exists(pdf_path):
            pdf_url = f"{settings.BACKEND_PUBLIC_URL}/docs/{settings.SERVICES_PDF_FILENAME}"
            logger.info(f"Enviando PDF de serviços para {phone[:6]}***")
            await whatsapp.send_document(
                phone=phone,
                pdf_url=pdf_url,
                filename=settings.SERVICES_PDF_FILENAME,
                caption="📄 Segue nossa tabela completa de serviços e valores!"
            )

    # 3. Registro Automático se todos os dados essenciais estiverem preenchidos
    if (session.get("name") and
        session.get("cpf") and
        session.get("service") and
        session.get("appointment_date")):
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

                if not existing:
                    logger.info(f"Registrando agendamento de {session['name']}...")
                    new_client = ClientWeb(
                        name=session["name"],
                        cpf=session["cpf"],
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service=service_name,
                        profile_pic=f"https://api.dicebear.com/7.x/adventurer/svg?seed={session['name']}",
                        appointment_date=session["appointment_date"],
                        slot_id=slot_id,
                        slot_date=slot_date_obj,
                        upsell_success=session.get("upsell_success", False),
                        upsell_service=session.get("upsell_service"),
                        status="pending",
                        exam_id=exam_id
                    )
                    db.add(new_client)
                    await db.commit()
                    logger.info("Agendamento registrado como pendente com sucesso!")
                else:
                    logger.info(f"Atualizando agendamento para {phone}...")
                    existing.name = session["name"]
                    existing.cpf = session["cpf"]
                    existing.service = service_name
                    existing.appointment_date = session["appointment_date"]
                    existing.slot_id = slot_id
                    existing.slot_date = slot_date_obj
                    existing.upsell_success = session.get("upsell_success", False)
                    existing.upsell_service = session.get("upsell_service")
                    existing.exam_id = exam_id
                    await db.commit()
                    logger.info("Agendamento atualizado com sucesso!")

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
                    confirm_msg += "\nSua consulta será confirmada em até *24 horas*! Te avisaremos aqui. 😊"
                    await whatsapp.send_message(phone, confirm_msg)
            except Exception as e:
                logger.error(f"Erro ao salvar agendamento automático: {e}")


    session = await sess.add_to_history(session, "user", censored_text)
    session = await sess.add_to_history(session, "assistant", response)
    await sess.save_session(phone, session)
