from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama3-8b-8192"
    AI_CONFIDENCE_THRESHOLD: float = 0.70

    DATABASE_URL: str = "sqlite+aiosqlite:///./agent.db"
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL_SECONDS: int = 3600

    HUMAN_PHONE: str
    MAX_AI_ATTEMPTS: int = 3
    WHATSAPP_API_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
