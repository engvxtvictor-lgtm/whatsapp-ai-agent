from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from backend.system.auth import verify_password, create_access_token
from backend.system.database import get_db
from backend.system.models.web_models import AdminWeb

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        AdminWeb.__table__.select().where(AdminWeb.email == request.email)
    )
    admin = result.fetchone()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # admin is a Row object, use _mapping to get a dict-like interface
    admin_dict = dict(admin._mapping)
    if not verify_password(request.password, admin_dict["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": admin_dict["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_current_admin(current_admin: dict = Depends(lambda token: None)):
    # Placeholder, will be overridden by dependency injection in real use
    return {"email": current_admin.get("email") if current_admin else None}
