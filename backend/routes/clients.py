from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.system.database import get_db
from backend.system.dependencies import get_current_admin
from backend.system.models.web_models import ClientWeb, AdminWeb
from backend.core.security import encrypt_payload, decrypt_payload

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_admin)])

@router.get("/", response_model=List[dict])
async def list_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(ClientWeb.__table__.select())
    clients = result.fetchall()
    # Return plain dicts (decrypted fields if needed)
    return [dict(row) for row in clients]

@router.get("/{client_id}", response_model=dict)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(ClientWeb.__table__.select().where(ClientWeb.id == client_id))
    client = result.fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(client)

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_client(payload: dict, db: AsyncSession = Depends(get_db)):
    # Encrypt sensitive fields before persisting
    if "cpf" in payload:
        payload["cpf"] = encrypt_payload({"value": payload["cpf"]})
    if "phone" in payload:
        payload["phone"] = encrypt_payload({"value": payload["phone"]})
    new_client = ClientWeb(**payload)
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return dict(new_client)

@router.put("/{client_id}", response_model=dict)
async def update_client(client_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(ClientWeb.__table__.select().where(ClientWeb.id == client_id))
    client = result.fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Update fields
    for key, value in payload.items():
        if key in ["cpf", "phone"]:
            value = encrypt_payload({"value": value})
        setattr(client, key, value)
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return dict(client)

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(ClientWeb.__table__.delete().where(ClientWeb.id == client_id))
    await db.commit()
    return None
