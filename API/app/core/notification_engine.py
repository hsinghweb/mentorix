from __future__ import annotations

from collections import deque
from datetime import datetime

from app.core.event_bus import event_bus


class NotificationEngine:
    def __init__(self):
        self._buffer: deque[dict] = deque(maxlen=500)

    async def notify(
        self,
        *,
        source: str,
        title: str,
        body: str,
        severity: str = "info",
        metadata: dict | None = None,
    ) -> dict:
        notification = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "title": title,
            "body": body,
            "severity": severity,
            "metadata": metadata or {},
        }
        self._buffer.appendleft(notification)
        await event_bus.publish("notification", "notification_engine", notification)
        return notification

    def list_notifications(self, limit: int = 50) -> list[dict]:
        return list(self._buffer)[: max(1, min(limit, 500))]


notification_engine = NotificationEngine()
