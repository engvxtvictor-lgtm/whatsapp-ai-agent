import sys, os, asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.system.auth import get_password_hash
from backend.system.database import AsyncSession
from backend.system.models.web_models import AdminWeb

async def seed():
    async with AsyncSession() as session:
        # Ensure password_hash column exists (for legacy DBs)
        from sqlalchemy import text
        await session.execute(text("ALTER TABLE web_admins ADD COLUMN IF NOT EXISTS password_hash VARCHAR"))
        await session.commit()
        # Verifica se já existe admin
        result = await session.execute(AdminWeb.__table__.select().where(AdminWeb.email == "admin@exemplo.com"))
        if result.fetchone():
            print("Admin já existe, nada a fazer.")
            return
        admin = AdminWeb(
            name="Admin Teste",
            email="admin@exemplo.com",
            password_hash=get_password_hash("senha123"),
            role="admin",
            avatar=None,
        )
        session.add(admin)
        await session.commit()
        print("Admin de teste criado com sucesso.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed())

