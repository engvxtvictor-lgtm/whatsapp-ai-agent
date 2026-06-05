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
    from sqlalchemy import select
    from backend.system.auth import get_password_hash
    
    result = await db.execute(select(AdminWeb).where(AdminWeb.email == request.email))
    admin = result.scalar_one_or_none()
    
    if not admin:
        # MODO DE EMERGÊNCIA: Auto-provisionar o admin mestre se não existir
        if request.email == "admin@lumina.com" and request.password == "senha123":
            admin = AdminWeb(
                name="Administrador Principal",
                email="admin@lumina.com",
                password_hash=get_password_hash("senha123"),
                role="Administrador",
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Admin"
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            
    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    access_token = create_access_token(data={"sub": admin.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_current_admin(current_admin: dict = Depends(lambda token: None)):
    # Placeholder, will be overridden by dependency injection in real use
    return {"email": current_admin.get("email") if current_admin else None}
