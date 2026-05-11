from fastapi import APIRouter, Request, BackgroundTasks
from app.services import session as sess
from app.services import ai_service, faq_service, whatsapp
from app.core.config import settings
from app.utils.logger import logger

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
    response, confidence = await ai_service.get_response(text, session["history"], context)
    session["ai_attempts"] += 1

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

    session = await sess.add_to_history(session, "user", text)
    session = await sess.add_to_history(session, "assistant", response)
    await sess.save_session(phone, session)