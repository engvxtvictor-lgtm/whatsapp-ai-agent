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

        # v3: Garante slots de sábado de manhã sem duplicar em bancos já configurados.
        saturday_hours = ["08:00", "09:00", "10:00", "11:00"]
        for hour in saturday_hours:
            try:
                await session.execute(
                    text(
                        """
                        INSERT INTO web_schedule_slots (weekday, time_str, max_patients, is_active)
                        SELECT 5, CAST(:hour AS VARCHAR), 1, TRUE
                        WHERE NOT EXISTS (
                            SELECT 1 FROM web_schedule_slots
                            WHERE weekday = 5 AND time_str = CAST(:hour AS VARCHAR)
                        )
                        """
                    ),
                    {"hour": hour},
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Erro ao garantir slot de sábado {hour}: {e}")

        # Post-migration: Atualizar senhas vazias para 'senha123'
        try:
            import bcrypt
            hashed_pw = bcrypt.hashpw("senha123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # 1. Update senhas vazias
            await session.execute(
                text("UPDATE web_admins SET password_hash = :hash WHERE password_hash = ''"),
                {"hash": hashed_pw}
            )
            
            # 2. Seed default admin if table is empty
            result = await session.execute(text("SELECT COUNT(*) FROM web_admins"))
            count = result.scalar()
            if count == 0:
                from backend.system.models.web_models import AdminWeb
                admin = AdminWeb(
                    name="Administrador Principal",
                    email="admin@lumina.com",
                    password_hash=hashed_pw,
                    role="Administrador",
                    avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Admin"
                )
                session.add(admin)
                logger.info("Administrador padrão criado com sucesso (admin@lumina.com).")
                
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Erro ao atualizar senhas/criar admin padrão: {e}")

    logger.info("Migrações concluídas.")
