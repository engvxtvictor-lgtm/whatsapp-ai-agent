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

    async def _mock_send(p, t):
        captured.append(t)
        return True

    async def _mock_escalation(p):
        captured.append("Vou te transferir para um atendente agora. Aguarde um momento! 🙏")

    async def _mock_notify(p, m):
        pass

    async with _lock:
        whatsapp.send_message = _mock_send
        whatsapp.send_escalation = _mock_escalation
        whatsapp.notify_agent = _mock_notify
        try:
            await handle(phone, text)
        finally:
            whatsapp.send_message = original_send
            whatsapp.send_escalation = original_escalation
            whatsapp.notify_agent = original_notify

    return {"messages": captured}


@router.delete("/session/{phone}")
async def clear_test_session(phone: str):
    await sess.redis_client.delete(f"{sess.PREFIX}{phone}")
    return {"cleared": True}
