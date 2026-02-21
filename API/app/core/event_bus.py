import asyncio
from collections import deque
from datetime import datetime


class EventBus:
    def __init__(self, history_size: int = 200):
        self._subscribers: list[asyncio.Queue] = []
        self._history: deque[dict] = deque(maxlen=history_size)
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, source: str, data: dict) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "source": source,
            "data": data,
        }
        async with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except Exception:
                continue

    async def subscribe(self, replay_last: int = 10) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
            history = list(self._history)[-replay_last:]
        for event in history:
            queue.put_nowait(event)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def history(self) -> list[dict]:
        return list(self._history)


event_bus = EventBus()
