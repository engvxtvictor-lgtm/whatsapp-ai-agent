from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    # OpenAI (ChatGPT)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Agente de Segurança / Redundância
    SECONDARY_API_KEY: Optional[str] = None
    SECONDARY_AI_MODEL: str = "gemini/gemini-1.5-flash"
    AI_TIMEOUT_SECONDS: int = 15

    AI_CONFIDENCE_THRESHOLD: float = 0.70

    # Banco de Dados e Cache
    DATABASE_URL: str = "sqlite+aiosqlite:///./agent.db"
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL_SECONDS: int = 3600

    # Configurações do Agente
    HUMAN_PHONE: str = "5511999999999"
    MAX_AI_ATTEMPTS: int = 3
    WHATSAPP_API_URL: str = "http://localhost:3000"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    SERVICES_PDF_FILENAME: str = "lumina_nossos_servicos.pdf"

    # Modo de operação
    DEBUG: bool = False

    # CORS — em produção, defina explicitamente os domínios permitidos
    # Ex: ALLOWED_ORIGINS=["https://app.lumina.com.br","https://www.lumina.com.br"]
    ALLOWED_ORIGINS: List[str] = ["*"]

    # JWT — RECOMENDADO: defina JWT_SECRET_KEY no .env com valor forte e único
    JWT_SECRET_KEY: str = "fallback_secret_lumina_key_12345"  # Fallback caso não exista no .env
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
