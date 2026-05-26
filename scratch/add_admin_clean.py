import sys, os, asyncio
from sqlalchemy import text

# Ensure project root is on sys.path for imports
sys.path.append(os.path.abspath('.'))

from backend.system.auth import get_password_hash
from backend.system.database import engine, AsyncSession
from backend.system.models.web_models import AdminWeb

async def ensure_password_hash_column():
    """Create password_hash column (nullable), clean rows, then make NOT NULL.
    Any existing rows without a password_hash are deleted as requested.
    """
    async with engine.begin() as conn:
        # 1️⃣ Add column if missing (allow NULL temporarily)
        await conn.execute(
            text(
                """
                ALTER TABLE web_admins
                ADD COLUMN IF NOT EXISTS password_hash VARCHAR
                """
            )
        )
        # 2️⃣ Delete rows where password_hash is NULL (or column missing values)
        await conn.execute(
            text("DELETE FROM web_admins WHERE password_hash IS NULL")
        )
        # 3️⃣ Set column to NOT NULL now that no null rows exist
        await conn.execute(
            text(
                """
                ALTER TABLE web_admins
                ALTER COLUMN password_hash SET NOT NULL
                """
            )
        )
        print("🔧 password_hash column ensured as NOT NULL – rows without it removed.")

async def insert_admin():
    async with AsyncSession() as db:
        admin = AdminWeb(
            name="Cadu Portela",
            email="caduportela2006@gmail.com",
            password_hash=get_password_hash("123456"),
            role="admin",
            avatar=None,
        )
        db.add(admin)
        await db.commit()
        print("✅ Admin record inserted.")

async def main():
    await ensure_password_hash_column()
    await insert_admin()

if __name__ == "__main__":
    asyncio.run(main())
