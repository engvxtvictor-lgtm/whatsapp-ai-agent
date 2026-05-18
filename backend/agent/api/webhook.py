from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy import select
from backend.agent.services import session as sess
from backend.agent.services import ai_service, faq_service, whatsapp
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ClientWeb

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
        for key in ["name", "cpf", "service", "appointment_date", "upsell_success", "upsell_service"]:
            if metadata.get(key) is not None and metadata.get(key) != "":
                if key == "cpf":
                    # Evita sobrescrever o CPF completo na sessão caso a IA devolva a versão censurada
                    if "*" in str(metadata[key]):
                        continue
                session[key] = metadata[key]

    if confidence >= settings.AI_CONFIDENCE_THRESHOLD:
        await whatsapp.send_message(phone, response)
    elif session["ai_attempts"] >= settings.MAX_AI_ATTEMPTS or confidence < 0.3:
        await whatsapp.send_escalation(phone)
        await whatsapp.notify_agent(phone, censored_text)
        session["escalated"] = True
    else:
        await whatsapp.send_message(phone,
            response + "\n\n_Caso queira falar com um atendente, é só pedir!_"
        )

    # 3. Registro Automático se todos os dados essenciais estiverem preenchidos
    if (session.get("name") and 
        session.get("cpf") and 
        session.get("service") and 
        session.get("appointment_date")):
        
        # Verifica se o cliente já não foi registrado para esta consulta/horário
        async with AsyncSession() as db:
            try:
                stmt = select(ClientWeb).where(
                    ClientWeb.phone == phone,
                    ClientWeb.appointment_date == session["appointment_date"]
                )
                result = await db.execute(stmt)
                existing = result.scalars().first()
                
                if not existing:
                    logger.info(f"Dados completos capturados. Registrando agendamento pendente de {session['name']} no banco de dados...")
                    new_client = ClientWeb(
                        name=session["name"],
                        cpf=session["cpf"],
                        phone=phone,
                        source=session.get("source", "whatsapp"),
                        service=session["service"],
                        profile_pic=f"https://api.dicebear.com/7.x/adventurer/svg?seed={session['name']}",
                        appointment_date=session["appointment_date"],
                        upsell_success=session.get("upsell_success", False),
                        upsell_service=session.get("upsell_service"),
                        status="pending"
                    )
                    db.add(new_client)
                    await db.commit()
                    logger.info("Agendamento registrado como pendente com sucesso!")
                    
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
