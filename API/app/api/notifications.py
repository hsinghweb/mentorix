from __future__ import annotations

from fastapi import APIRouter

from app.core.notification_engine import notification_engine

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(limit: int = 50):
    return {"items": notification_engine.list_notifications(limit=limit)}


@router.post("/send")
async def send_notification(payload: dict):
    note = await notification_engine.notify(
        source=str(payload.get("source", "manual")),
        title=str(payload.get("title", "Notification")),
        body=str(payload.get("body", "")),
        severity=str(payload.get("severity", "info")),
        metadata=payload.get("metadata", {}),
    )
    return note
