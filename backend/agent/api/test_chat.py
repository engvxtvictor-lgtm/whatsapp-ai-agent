import asyncio
from fastapi import APIRouter, Request
from backend.agent.api.webhook import handle
from backend.agent.services import whatsapp
from backend.agent.services import session as sess

router = APIRouter(prefix="/test")
_lock = asyncio.Lock()


@router.post("/chat")
async def test_chat(request: Request):
    body = await request.json()
    phone = body.get("phone", "5500000000001")
    text = body.get("message", "")

    if not text:
        return {"messages": []}

    captured = []
    original_send = whatsapp.send_message
    original_escalation = whatsapp.send_escalation
    original_notify = whatsapp.notify_agent
    original_document = whatsapp.send_document

    async def _mock_send(p, t):
        captured.append(t)
        return True

    async def _mock_escalation(p):
        captured.append("Vou te transferir para um atendente agora. Aguarde um momento! 🙏")

    async def _mock_notify(p, m):
        pass

    async def _mock_document(phone, pdf_url, filename, caption):
        captured.append(f"[📎 Documento Anexado: {filename}]\n{caption}")
        return True

    async with _lock:
        whatsapp.send_message = _mock_send
        whatsapp.send_escalation = _mock_escalation
        whatsapp.notify_agent = _mock_notify
        whatsapp.send_document = _mock_document
        try:
            await handle(phone, text)
        finally:
            whatsapp.send_message = original_send
            whatsapp.send_escalation = original_escalation
            whatsapp.notify_agent = original_notify
            whatsapp.send_document = original_document

    return {"messages": captured}


@router.get("/chat/{phone}/history")
async def get_chat_history(phone: str):
    session = await sess.get_session(phone)
    messages = []
    for h in session.get("history", []):
        role = "user" if h["role"] == "user" else "bot"
        messages.append({"role": role, "text": h["content"]})
    return {"messages": messages}


@router.delete("/session/{phone}")
async def clear_test_session(phone: str):
    await sess.redis_client.delete(f"{sess.PREFIX}{phone}")
    return {"cleared": True}
