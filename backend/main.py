import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware

from backend.agent.api.webhook import router as webhook_router
from backend.agent.api.dashboard import router as dashboard_router
from backend.agent.api.test_chat import router as test_router
from backend.agent.api.auth import router as auth_router
from backend.agent.services.followup_scheduler import create_scheduler
import backend.system.models  # Garante que os modelos sejam carregados para criação das tabelas
from backend.system.database import create_tables
from backend.system.config import settings

logger = logging.getLogger(__name__)


async def migrate_db():
    from sqlalchemy import text
    from backend.system.database import AsyncSession
    
    logger.info("Executando migrações de colunas do banco de dados...")
    
    async with AsyncSession() as session:
        # 1. Migrações de colunas (ALTER TABLE)
        # Tenta adicionar is_recurring
        try:
            await session.execute(text("ALTER TABLE web_followups ADD COLUMN is_recurring BOOLEAN DEFAULT FALSE NOT NULL;"))
            await session.commit()
            logger.info("Coluna is_recurring adicionada à tabela web_followups.")
        except Exception:
            await session.rollback()
            
        # Tenta adicionar recurrence_interval
        try:
            await session.execute(text("ALTER TABLE web_followups ADD COLUMN recurrence_interval INTEGER DEFAULT 0;"))
            await session.commit()
            logger.info("Coluna recurrence_interval adicionada à tabela web_followups.")
        except Exception:
            await session.rollback()
            
    logger.info("Migrações de colunas concluídas com sucesso.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando {settings.APP_NAME if hasattr(settings, 'APP_NAME') else 'WhatsApp AI Agent'}...")
    await create_tables()
    logger.info("Banco de dados pronto.")
    await migrate_db()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler de follow-up iniciado.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Encerrando aplicação.")


app = FastAPI(title="WhatsApp AI Agent", version="1.0.0", lifespan=lifespan)

# CORS — permite chamadas do frontend (porta 8080) e qualquer origem em dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de Rotas
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(test_router)
app.include_router(auth_router)


# Rota para servir a página inicial do Frontend
@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")


@app.get("/test")
async def test_chat_page():
    return FileResponse("frontend/test_chat.html")


# Servir a pasta frontend como arquivos estáticos (disabled — agora servido via Nginx)
# app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Servir documentos (PDFs) como arquivos estáticos
os.makedirs("backend/agent/docs", exist_ok=True)
app.mount("/docs-files", StaticFiles(directory="backend/agent/docs"), name="docs")


@app.get("/health")
async def health():
    return {"status": "ok"}
