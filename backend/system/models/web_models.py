from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.system.database import Base


class ClientWeb(Base):
    __tablename__ = "web_clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="whatsapp")  # whatsapp ou instagram
    service: Mapped[str] = mapped_column(String(50), nullable=False)      # Clareamento, Limpeza, Canal, Implante, etc.
    profile_pic: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # Novos campos para agendamento e upsell
    appointment_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Horário (dia) desejado para consulta
    upsell_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Se conseguiu fazer upsell
    upsell_service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # Qual foi o serviço do upsell
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdminWeb(Base):
    __tablename__ = "web_admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)        # Administrador, Atendente, Dentista, etc.
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ServiceWeb(Base):
    __tablename__ = "web_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)       # Nome do procedimento (ex: Clareamento, Limpeza)
    price: Mapped[float] = mapped_column(nullable=False)                 # Preço médio do serviço
    necessity: Mapped[str] = mapped_column(String(255), nullable=False)  # Necessidade/Motivação para ofertar (ex: indicação estética)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

