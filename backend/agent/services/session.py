import json
import redis.asyncio as aioredis
from backend.system.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
PREFIX = "session:"


async def get_session(phone: str) -> dict:
    data = await redis_client.get(f"{PREFIX}{phone}")
    if data:
        # Garante retrocompatibilidade se a sessão antiga não tiver os novos campos
        session = json.loads(data)
        defaults = {
            "name": None,
            "cpf": None,
            "service": None,
            "appointment_date": None,
            "upsell_success": False,
            "upsell_service": None,
            "source": "whatsapp"
        }
        for key, value in defaults.items():
            if key not in session:
                session[key] = value
        return session
        
    return {
        "phone": phone,
        "history": [],
        "ai_attempts": 0,
        "escalated": False,
        "name": None,
        "cpf": None,
        "service": None,
        "appointment_date": None,
        "upsell_success": False,
        "upsell_service": None,
        "source": "whatsapp"
    }


async def save_session(phone: str, session: dict):
    await redis_client.setex(
        f"{PREFIX}{phone}",
        settings.SESSION_TTL_SECONDS,
        json.dumps(session)
    )


async def delete_session(phone: str):
    await redis_client.delete(f"{PREFIX}{phone}")



async def add_to_history(session: dict, role: str, content: str) -> dict:
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-20:]
    return session
