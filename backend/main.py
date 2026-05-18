from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from backend.agent.api.webhook import router as webhook_router
from backend.agent.api.dashboard import router as dashboard_router
import backend.system.models  # Garante que os modelos sejam carregados para criação das tabelas
from backend.system.database import create_tables
from backend.system.config import settings
from backend.system.logger import logger


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
