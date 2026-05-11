import json
import redis.asyncio as aioredis
from app.core.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
PREFIX = "session:"


async def get_session(phone: str) -> dict:
    data = await redis_client.get(f"{PREFIX}{phone}")
    if data:
        return json.loads(data)
    return {"phone": phone, "history": [], "ai_attempts": 0, "escalated": False}


async def save_session(phone: str, session: dict):
    await redis_client.setex(
        f"{PREFIX}{phone}",
        settings.SESSION_TTL_SECONDS,
        json.dumps(session)
    )


async def add_to_history(session: dict, role: str, content: str) -> dict:
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-20:]
    return session