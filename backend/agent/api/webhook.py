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

    # 1. tenta FAQ
    answer, score = faq_service.search_faq(text)
    if answer and score >= 0.6:
        await whatsapp.send_message(phone, answer)
        session = await sess.add_to_history(session, "user", text)
        session = await sess.add_to_history(session, "assistant", answer)
        await sess.save_session(phone, session)
        return

    # 2. consulta IA
    context = faq_service.get_context(text)
    response, confidence, metadata = await ai_service.get_response(text, session["history"], context)
    session["ai_attempts"] += 1

    # Atualiza dados da sessão caso a IA tenha capturado novos metadados
    if metadata:
        for key in ["name", "cpf", "service", "appointment_date", "upsell_success", "upsell_service"]:
            if metadata.get(key) is not None and metadata.get(key) != "":
                session[key] = metadata[key]

    if confidence >= settings.AI_CONFIDENCE_THRESHOLD:
        await whatsapp.send_message(phone, response)
    elif session["ai_attempts"] >= settings.MAX_AI_ATTEMPTS or confidence < 0.3:
        await whatsapp.send_escalation(phone)
        await whatsapp.notify_agent(phone, text)
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
                    logger.info(f"Dados completos capturados. Registrando agendamento de {session['name']} no banco de dados...")
                    new_client = ClientWeb(
                        name=session["name"],
                        cpf=session["cpf"],
                        phone=phone,
                        source="whatsapp",
                        service=session["service"],
                        profile_pic=f"https://api.dicebear.com/7.x/adventurer/svg?seed={session['name']}",
                        appointment_date=session["appointment_date"],
                        upsell_success=session.get("upsell_success", False),
                        upsell_service=session.get("upsell_service")
                    )
                    db.add(new_client)
                    await db.commit()
                    logger.info("Agendamento registrado com sucesso!")
                    
                    # Notifica no WhatsApp a confirmação estrita do agendamento
                    confirm_msg = (
                        f"✅ *Consulta Confirmada!*\n\n"
                        f"Olá *{session['name']}*, seu agendamento de *{session['service']}* foi registrado com sucesso!\n"
                        f"📅 *Data/Hora:* {session['appointment_date']}\n"
                    )
                    if session.get("upsell_success") and session.get("upsell_service"):
                        confirm_msg += f"➕ *Serviço Adicional (Upsell):* {session['upsell_service']}\n"
                    
                    confirm_msg += "\nTe aguardamos na clínica! Qualquer dúvida, estamos à disposição. 😊"
                    await whatsapp.send_message(phone, confirm_msg)
            except Exception as e:
                logger.error(f"Erro ao salvar agendamento automático: {e}")

    session = await sess.add_to_history(session, "user", text)
    session = await sess.add_to_history(session, "assistant", response)
    await sess.save_session(phone, session)
