import sys, os, asyncio
sys.path.append(os.path.abspath('.'))
from sqlalchemy import text
from backend.system.database import engine

async def add_column():
    async with engine.begin() as conn:
        # Add password_hash column if it doesn't exist
        await conn.execute(text('ALTER TABLE web_admins ADD COLUMN IF NOT EXISTS password_hash VARCHAR NOT NULL'))
        print('🔧 password_hash column added (if it was missing).')

if __name__ == '__main__':
    asyncio.run(add_column())
