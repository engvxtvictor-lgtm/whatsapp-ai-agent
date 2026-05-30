import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware
import os

from backend.agent.api.webhook import router as webhook_router
from backend.agent.api.dashboard import router as dashboard_router
from backend.agent.api.auth import router as auth_router
from backend.agent.services.followup_scheduler import create_scheduler
import backend.system.models  # Garante que os modelos sejam carregados para criação das tabelas
from backend.system.database import create_tables
from backend.system.config import settings
from backend.system.migrations import run_migrations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando WhatsApp AI Agent...")
    await create_tables()
    logger.info("Banco de dados pronto.")
    await run_migrations()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler de follow-up iniciado.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Encerrando aplicação.")


app = FastAPI(
    title="WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan,
    # Docs desabilitados em produção para não expor a API publicamente
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS — controlado pela variável ALLOWED_ORIGINS no .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de Rotas
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(auth_router)

# Servir documentos (PDFs) como arquivos estáticos
os.makedirs("backend/agent/docs", exist_ok=True)
app.mount("/docs-files", StaticFiles(directory="backend/agent/docs"), name="docs")


@app.get("/health")
async def health():
    return {"status": "ok"}
