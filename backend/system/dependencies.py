from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from backend.system.config import settings
from backend.system.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend.system.models.web_models import AdminWeb

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_admin(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        admin_email: str = payload.get("sub")
        if admin_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    result = await db.execute(
        AdminWeb.__table__.select().where(AdminWeb.email == admin_email)
    )
    admin = result.fetchone()
    if admin is None:
        raise credentials_exception
    return admin
