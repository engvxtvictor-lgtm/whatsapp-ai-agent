"""
Módulo de migrações incrementais do banco de dados.

Executado automaticamente no startup do FastAPI (lifespan).
Cada migração usa try/except para ser idempotente — se a coluna
já existir, o erro é ignorado silenciosamente.

Para migrações complexas, considere adotar o Alembic.
"""
import logging
from sqlalchemy import text
from backend.system.database import AsyncSession

logger = logging.getLogger(__name__)


async def run_migrations() -> None:
    """Executa todas as migrações incrementais do schema."""
    logger.info("Executando migrações de schema...")

    async with AsyncSession() as session:
        migrations = [
            # v1: Adiciona suporte a follow-ups recorrentes
            (
                "ALTER TABLE web_followups ADD COLUMN is_recurring BOOLEAN DEFAULT FALSE NOT NULL;",
                "is_recurring em web_followups"
            ),
            (
                "ALTER TABLE web_followups ADD COLUMN recurrence_interval INTEGER DEFAULT 0;",
                "recurrence_interval em web_followups"
            ),
            # v2: Adiciona hash de senha aos administradores
            (
                "ALTER TABLE web_admins ADD COLUMN password_hash VARCHAR DEFAULT '' NOT NULL;",
                "password_hash em web_admins"
            ),
        ]

        for sql, description in migrations:
            try:
                await session.execute(text(sql))
                await session.commit()
                logger.info(f"Migração aplicada: {description}")
            except Exception:
                await session.rollback()
                # Coluna já existe — ignorar silenciosamente
                logger.debug(f"Migração já aplicada (ignorada): {description}")

    logger.info("Migrações concluídas.")
