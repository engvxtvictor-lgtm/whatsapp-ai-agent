import httpx
from backend.system.config import settings
from backend.system.logger import logger

async def send_message(phone: str, text: str) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            url = f"{settings.WHATSAPP_API_URL}/send"
            r = await client.post(url, json={"phone": phone, "text": text})
            logger.info(f"Mensagem enviada para {phone[:6]}***")
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False


async def send_escalation(phone: str):
    await send_message(phone,
        "Vou te transferir para um atendente agora. Aguarde um momento! 🙏"
    )


async def notify_agent(user_phone: str, message: str):
    await send_message(settings.HUMAN_PHONE,
        f"🔔 *Nova escalação*\n\nCliente: {user_phone}\nMensagem: _{message}_"
    )
