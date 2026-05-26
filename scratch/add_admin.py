import sys, os, asyncio
# Ensure project root is in sys.path for imports
sys.path.append(os.path.abspath('.'))

from backend.system.auth import get_password_hash
from backend.system.database import AsyncSession
from backend.system.models.web_models import AdminWeb

async def main():
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

if __name__ == "__main__":
    asyncio.run(main())
