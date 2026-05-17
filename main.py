from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.api.webhook import router as webhook_router
from app.api.dashboard import router as dashboard_router
import app.models  # Garante que os modelos sejam carregados para criação das tabelas
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

# Registro de Rotas
app.include_router(webhook_router)
app.include_router(dashboard_router)


# Rota para servir a página inicial do Frontend
@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")


# Servir a pasta frontend como arquivos estáticos (CSS, JS, Imagens)
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/health")
async def health():
    return {"status": "ok"}