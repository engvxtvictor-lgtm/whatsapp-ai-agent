import json
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.system.config import settings
from backend.system.database import get_db
from backend.system.dependencies import get_current_admin
from backend.system.models.web_models import WhatsappEventLogWeb, WhatsappSessionWeb

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


async def _request_baileys(method: str, path: str, **kwargs) -> Any:
    url = f"{settings.WHATSAPP_API_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Gateway WhatsApp indisponivel: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json()
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


async def _record_event(
    db: AsyncSession,
    event_type: str,
    status: dict | None = None,
    message: str | None = None,
) -> None:
    status = status or {}
    clinic_id = status.get("clinicId") or "default"
    session_id = status.get("sessionId") or "default"

    result = await db.execute(select(WhatsappSessionWeb).where(WhatsappSessionWeb.clinic_id == clinic_id))
    session = result.scalars().first()
    if not session:
        session = WhatsappSessionWeb(clinic_id=clinic_id, session_id=session_id)
        db.add(session)

    session.session_id = session_id
    session.status = status.get("status") or session.status
    session.connected_at = _parse_dt(status.get("connectedAt"))
    session.last_activity_at = _parse_dt(status.get("lastActivityAt"))
    session.last_reconnect_at = _parse_dt(status.get("lastReconnectAt"))
    session.disconnect_reason = status.get("disconnectReason")
    session.whatsapp_version = status.get("whatsappVersion")
    session.connected_number = status.get("connectedNumber")
    session.qr_updated_at = _parse_dt(status.get("qrUpdatedAt"))
    session.updated_at = datetime.utcnow()

    db.add(
        WhatsappEventLogWeb(
            clinic_id=clinic_id,
            session_id=session_id,
            event_type=event_type,
            status=status.get("status"),
            message=message,
            payload=json.dumps(status, ensure_ascii=False)[:10000],
        )
    )
    await db.commit()


@router.get("/status")
async def whatsapp_status(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    status = await _request_baileys("GET", "/status")
    await _record_event(db, "status_sync", status)
    return status


@router.get("/qrcode")
async def whatsapp_qrcode(_admin=Depends(get_current_admin)):
    return await _request_baileys("GET", "/qrcode")


@router.post("/connect")
async def whatsapp_connect(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    status = await _request_baileys("POST", "/connect")
    await _record_event(db, "connect_requested", status)
    return status


@router.post("/reconnect")
async def whatsapp_reconnect(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    status = await _request_baileys("POST", "/reconnect")
    await _record_event(db, "reconnect_requested", status)
    return status


@router.post("/disconnect")
async def whatsapp_disconnect(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    status = await _request_baileys("POST", "/disconnect")
    await _record_event(db, "disconnect_requested", status)
    return status


@router.post("/logout")
async def whatsapp_logout(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    status = await _request_baileys("POST", "/logout")
    await _record_event(db, "logout_requested", status)
    return status


@router.get("/info")
async def whatsapp_info(_admin=Depends(get_current_admin)):
    return await _request_baileys("GET", "/info")


@router.get("/health")
async def whatsapp_health(_admin=Depends(get_current_admin)):
    return await _request_baileys("GET", "/health")


@router.get("/logs")
async def whatsapp_logs(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(
        select(WhatsappEventLogWeb).order_by(WhatsappEventLogWeb.id.desc()).limit(30)
    )
    logs = result.scalars().all()
    return [
        {
            "id": item.id,
            "clinic_id": item.clinic_id,
            "session_id": item.session_id,
            "event_type": item.event_type,
            "status": item.status,
            "message": item.message,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in logs
    ]


@router.get("/events")
async def whatsapp_events(token: str = Query(...)):
    try:
        jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token invalido") from exc

    async def stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"{settings.WHATSAPP_API_URL}/events") as response:
                async for chunk in response.aiter_text():
                    yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")
