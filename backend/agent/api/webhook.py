from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy import select
from backend.agent.services import session as sess
from backend.agent.services import ai_service, faq_service, whatsapp
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb, ExamWeb
import os

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

    session["ai_attempts"] += 1

    # Atualiza dados da sessão caso a IA tenha capturado novos metadados
    if metadata:
        for key in ["name", "cpf", "service", "appointment_date", "upsell_success", "upsell_service", "needs_human"]:
            if metadata.get(key) is not None and metadata.get(key) != "":
                if key == "cpf":
                    # Evita sobrescrever o CPF completo na sessão caso a IA devolva a versão censurada
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
        (confidence < 0.3) or
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
          # Verifica se o cliente já não foi registrado
        async with AsyncSession() as db:
            try:
                stmt = select(ClientWeb).where(ClientWeb.phone == phone)
                result = await db.execute(stmt)
                existing = result.scalars().first()
                
                # Resolve exam_id based on service name
                exam_id = None
                service_name = session["service"]
                exams_res = await db.execute(select(ExamWeb))
                exams = exams_res.scalars().all()
                for exam in exams:
                    if (service_name.lower() in exam.name.lower()) or (exam.name.lower() in service_name.lower()):
                        exam_id = exam.id
                        service_name = exam.name
                        break

                if not existing:
                    logger.info(f"Dados completos capturados. Registrando agendamento pendente de {session['name']} no banco de dados...")
                    new_client = ClientWeb(
                        name=session["name"],
                        cpf=session["cpf"],
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service=service_name,
                        profile_pic=f"https://api.dicebear.com/7.x/adventurer/svg?seed={session['name']}",
                        appointment_date=session["appointment_date"],
                        upsell_success=session.get("upsell_success", False),
                        upsell_service=session.get("upsell_service"),
                        status="pending",
                        exam_id=exam_id
                    )
                    db.add(new_client)
                    await db.commit()
                    logger.info("Agendamento registrado como pendente com sucesso!")
                else:
                    # Atualiza os dados do cliente existente (por exemplo, se já era um placeholder de atendimento humano)
                    logger.info(f"Atualizando agendamento para o cliente {phone} existente...")
                    existing.name = session["name"]
                    existing.cpf = session["cpf"]
                    existing.service = service_name
                    existing.appointment_date = session["appointment_date"]
                    existing.upsell_success = session.get("upsell_success", False)
                    existing.upsell_service = session.get("upsell_service")
                    existing.exam_id = exam_id
                    await db.commit()
                    logger.info("Agendamento atualizado com sucesso!")
                    
                    # Notifica no WhatsApp a solicitacao de agendamento em analise
                    confirm_msg = (
                        f"📅 *Agendamento Solicitado!*\n\n"
                        f"Olá *{session['name']}*, sua sugestão de consulta para *{session['service']}* foi enviada à nossa equipe.\n"
                        f"📅 *Data/Hora Sugerida:* {session['appointment_date']}\n"
                    )
                    if session.get("upsell_success") and session.get("upsell_service"):
                        confirm_msg += f"➕ *Serviço Adicional (Upsell):* {session['upsell_service']}\n"
                    
                    confirm_msg += "\nSua consulta será analisada e confirmada em até *24 horas* diretamente aqui no chat! Te avisaremos assim que for aprovada. 😊"
                    await whatsapp.send_message(phone, confirm_msg)
            except Exception as e:
                logger.error(f"Erro ao salvar agendamento automático: {e}")

    session = await sess.add_to_history(session, "user", censored_text)
    session = await sess.add_to_history(session, "assistant", response)
    await sess.save_session(phone, session)
