from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.system.database import get_db
from backend.system.dependencies import get_current_admin
from backend.system.models.web_models import AdminWeb

router = APIRouter(prefix="/admins", tags=["admins"], dependencies=[Depends(get_current_admin)])

@router.get("/", response_model=List[dict])
async def list_admins(db: AsyncSession = Depends(get_db)):
    result = await db.execute(AdminWeb.__table__.select())
    admins = result.fetchall()
    return [dict(row) for row in admins]

@router.get("/{admin_id}", response_model=dict)
async def get_admin(admin_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(AdminWeb.__table__.select().where(AdminWeb.id == admin_id))
    admin = result.fetchone()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return dict(admin)

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_admin(payload: dict, db: AsyncSession = Depends(get_db)):
    new_admin = AdminWeb(**payload)
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return dict(new_admin)

@router.put("/{admin_id}", response_model=dict)
async def update_admin(admin_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(AdminWeb.__table__.select().where(AdminWeb.id == admin_id))
    admin = result.fetchone()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    for key, value in payload.items():
        setattr(admin, key, value)
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return dict(admin)

@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(admin_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(AdminWeb.__table__.delete().where(AdminWeb.id == admin_id))
    await db.commit()
    return None
