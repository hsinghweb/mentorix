"""
Shared service helpers — extracted from route handlers for reuse.

These functions were duplicated or tightly coupled in route files.
Moving them here provides a single source of truth and reduces route file size.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_domain_logger
from app.memory.cache import redis_client
from app.mcp.client import execute_mcp
from app.mcp.contracts import MCPRequest
from app.core.llm_provider import get_llm_provider
from app.core.progress_stream import emit as progress_emit

logger = get_domain_logger(__name__)


# ── LLM Text Generation ────────────────────────────────────────────────

async def generate_text_with_mcp(
    prompt: str,
    *,
    role: str = "content_generator",
    operation_id: str | None = None,
) -> tuple[str | None, dict]:
    """
    Generate text via MCP with LLM fallback.

    If ``operation_id`` is provided, emits progress events to
    ``progress_stream`` so the frontend can show real-time status.
    """
    if operation_id:
        progress_emit(operation_id, "generating", f"Calling LLM ({role})…", progress=0.1)

    provider = get_llm_provider(role=role)

    async def _fallback() -> dict:
        text, meta = await provider.generate(prompt)
        if not text:
            raise RuntimeError("LLM provider returned empty output")
        return {"text": text, "meta": meta if isinstance(meta, dict) else {}, "role": role}

    response = await execute_mcp(
        MCPRequest(operation="llm.generate_text", payload={"prompt": prompt, "role": role}),
        fallback=_fallback,
    )

    if not response.ok:
        if operation_id:
            progress_emit(operation_id, "error", response.error or "mcp_failed", progress=1.0)
        return None, {"reason": response.error or "mcp_failed", "fallback_used": response.fallback_used}

    result = response.result if isinstance(response.result, dict) else {}
    text = result.get("text")
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}

    if operation_id:
        progress_emit(operation_id, "complete", "Text generated", progress=1.0)

    return (str(text) if text else None), meta


# ── Idempotency Cache ──────────────────────────────────────────────────

_idempotency_cache: dict[str, dict] = {}


async def get_idempotent_response(cache_key: str) -> dict | None:
    """Check Redis (then in-memory) for a cached idempotent response."""
    try:
        raw = await redis_client.get(cache_key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis unavailable for idempotency read: %s", exc)
    return _idempotency_cache.get(cache_key)


async def set_idempotent_response(cache_key: str, payload: dict) -> None:
    """Store an idempotent response in Redis + in-memory fallback."""
    _idempotency_cache[cache_key] = payload
    try:
        await redis_client.set(cache_key, json.dumps(payload), ex=3600)
    except Exception as exc:
        logger.warning("Redis unavailable for idempotency write: %s", exc)


# ── Engagement Logging ─────────────────────────────────────────────────

def log_engagement_event(
    db: AsyncSession,
    learner_id: UUID,
    event_type: str,
    duration_minutes: int = 0,
    details: dict | None = None,
) -> None:
    """Log a learner engagement event (login, reading, test, etc.)."""
    from app.models.entities import EngagementEvent

    db.add(
        EngagementEvent(
            learner_id=learner_id,
            event_type=event_type,
            duration_minutes=max(0, int(duration_minutes)),
            details=details or {},
        )
    )


# ── Login Streak ───────────────────────────────────────────────────────

async def compute_login_streak_days(db: AsyncSession, learner_id: UUID) -> int:
    """Count consecutive login days up to today."""
    from datetime import timedelta

    from app.models.entities import EngagementEvent

    rows = (
        await db.execute(
            select(EngagementEvent.created_at)
            .where(
                EngagementEvent.learner_id == learner_id,
                EngagementEvent.event_type == "login",
            )
            .order_by(EngagementEvent.created_at.desc())
            .limit(60)
        )
    ).scalars().all()
    if not rows:
        return 0
    dates = sorted({dt.astimezone(timezone.utc).date() for dt in rows}, reverse=True)
    streak = 0
    cursor = datetime.now(timezone.utc).date()
    for login_day in dates:
        if login_day == cursor:
            streak += 1
            cursor = cursor - timedelta(days=1)
            continue
        if streak == 0 and login_day == cursor - timedelta(days=1):
            streak += 1
            cursor = login_day - timedelta(days=1)
            continue
        if login_day < cursor:
            break
    return streak


# ── Revision Queue ─────────────────────────────────────────────────────

async def upsert_revision_queue_item(
    *,
    db: AsyncSession,
    learner_id: UUID,
    chapter: str,
    reason: str,
    priority: int = 1,
) -> None:
    """Insert or update a revision queue entry for a learner."""
    from app.models.entities import RevisionQueueItem

    existing = (
        await db.execute(
            select(RevisionQueueItem).where(
                RevisionQueueItem.learner_id == learner_id,
                RevisionQueueItem.chapter == chapter,
                RevisionQueueItem.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.priority = max(existing.priority, priority)
        existing.reason = reason
        existing.updated_at = datetime.now(timezone.utc)
        return
    db.add(
        RevisionQueueItem(
            learner_id=learner_id,
            chapter=chapter,
            status="pending",
            priority=priority,
            reason=reason,
        )
    )
