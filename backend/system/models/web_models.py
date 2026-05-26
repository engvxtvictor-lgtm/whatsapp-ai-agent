from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    
    # Agendamento e upsell
    appointment_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # texto legado
    slot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("web_schedule_slots.id"), nullable=True)
    slot_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # data real do agendamento
    upsell_success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    upsell_service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    exam_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("web_exams.id"), nullable=True)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    exam: Mapped[Optional["ExamWeb"]] = relationship("ExamWeb", back_populates="clients")
    slot: Mapped[Optional["ScheduleSlotWeb"]] = relationship("ScheduleSlotWeb", back_populates="clients")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class AdminWeb(Base):
    __tablename__ = "web_admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)  # BCrypt hash of password
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


class FollowupWeb(Base):
    __tablename__ = "web_followups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)       # Nome da regra (ex: Lembrete Semestral)
    service: Mapped[str] = mapped_column(String(50), nullable=False)     # Procedimento odontológico gatilho (ex: Limpeza)
    delay_days: Mapped[int] = mapped_column(nullable=False)              # Dias decorridos após a consulta (ex: 180)
    message_template: Mapped[str] = mapped_column(String(500), nullable=False) # Template da mensagem com placeholders
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False) # Status de atividade
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Se repete periodicamente
    recurrence_interval: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0) # Intervalo em dias
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExamWeb(Base):
    __tablename__ = "web_exams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)       # Nome do procedimento (ex: Raspagem, Implante)
    price: Mapped[float] = mapped_column(nullable=False)                 # Preço a partir de
    category: Mapped[str] = mapped_column(String(50), nullable=False)    # Categoria do exame/procedimento
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


    clients: Mapped[list["ClientWeb"]] = relationship("ClientWeb", back_populates="exam")


class ScheduleSlotWeb(Base):
    """Grade de horários disponíveis configurada pelo admin."""
    __tablename__ = "web_schedule_slots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)       # 0=seg, 1=ter, ..., 6=dom
    time_str: Mapped[str] = mapped_column(String(5), nullable=False)    # ex: "09:00"
    max_patients: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    clients: Mapped[list["ClientWeb"]] = relationship("ClientWeb", back_populates="slot")


class FollowupLogWeb(Base):
    """Registra quais follow-ups já foram enviados para evitar duplicatas."""
    __tablename__ = "web_followup_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("web_clients.id"), nullable=False)
    followup_id: Mapped[int] = mapped_column(Integer, ForeignKey("web_followups.id"), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)




