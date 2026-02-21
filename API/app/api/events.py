from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.event_bus import event_bus

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def stream_events():
    queue = await event_bus.subscribe(replay_last=20)

    async def generator():
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            return
        finally:
            await event_bus.unsubscribe(queue)

    return StreamingResponse(generator(), media_type="text/event-stream")
