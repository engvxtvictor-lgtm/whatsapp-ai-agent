from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.webhook import router as webhook_router
from app.core.database import create_tables
from app.core.config import settings
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando {settings.APP_NAME if hasattr(settings, 'APP_NAME') else 'WhatsApp AI Agent'}...")
    await create_tables()
    logger.info("Banco de dados pronto.")
    yield
    logger.info("Encerrando aplicação.")


app = FastAPI(title="WhatsApp AI Agent", version="1.0.0", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok"}