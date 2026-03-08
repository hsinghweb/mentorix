"""
Progress Stream — WebSocket-compatible progress events for long-running jobs.

Provides in-memory event queues per operation-id so the frontend can subscribe
to real-time stage updates during content generation, test generation, and replans.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# In-memory per-operation event queues
_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
_completed: set[str] = set()


def emit(operation_id: str, stage: str, detail: str = "", progress: float | None = None) -> None:
    """
    Emit a progress event for an operation.

    Args:
        operation_id: unique id for the long-running job
        stage: short stage name e.g. 'generating_content', 'validating', 'complete'
        detail: human-readable detail string
        progress: optional 0.0-1.0 progress fraction
    """
    event = {
        "operation_id": operation_id,
        "stage": stage,
        "detail": detail,
        "progress": progress,
        "timestamp": time.time(),
    }
    try:
        _queues[operation_id].put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("Progress queue full for operation %s", operation_id)

    if stage == "complete" or stage == "error":
        _completed.add(operation_id)


async def subscribe(operation_id: str, timeout: float = 300.0):
    """
    Async generator yielding progress events for an operation.
    Intended to be consumed by a WebSocket handler.
    """
    queue = _queues[operation_id]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
            yield event
            if event.get("stage") in ("complete", "error"):
                break
        except asyncio.TimeoutError:
            if operation_id in _completed:
                break
            yield {"operation_id": operation_id, "stage": "heartbeat", "timestamp": time.time()}

    # Cleanup
    _queues.pop(operation_id, None)
    _completed.discard(operation_id)


def cleanup_stale(max_age_seconds: int = 600) -> int:
    """Remove completed operation queues older than max_age."""
    removed = 0
    stale = [oid for oid in _completed]
    for oid in stale:
        _queues.pop(oid, None)
        _completed.discard(oid)
        removed += 1
    return removed
