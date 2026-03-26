"""
Rate limiter — Redis-backed sliding window rate limiting per learner.

Provides per-endpoint rate limits for LLM-intensive operations:
- Content generation: 10 requests / minute
- Test generation: 5 requests / minute
- Global API: 100 requests / second

Returns 429 Too Many Requests with Retry-After header.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.core.logging import get_domain_logger

logger = get_domain_logger(__name__, "security")


# ── Configuration ────────────────────────────────────────────────────

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "content_generation": (10, 60),     # 10 per 60s
    "test_generation": (5, 60),         # 5 per 60s
    "section_content": (15, 60),        # 15 per 60s
    "explain_question": (20, 60),       # 20 per 60s
    "global": (100, 1),                 # 100 per second
}


# ── In-memory fallback (when Redis unavailable) ─────────────────────

_windows: dict[str, list[float]] = {}


def _cleanup_window(key: str, window_seconds: int) -> None:
    """Remove expired entries from a sliding window."""
    now = time.time()
    cutoff = now - window_seconds
    if key in _windows:
        _windows[key] = [t for t in _windows[key] if t > cutoff]


async def check_rate_limit(
    identifier: str,
    endpoint: str,
    redis_client: Any = None,
) -> tuple[bool, dict[str, Any]]:
    """
    Check if a request is within rate limits.

    Args:
        identifier: Learner ID or IP address
        endpoint: Rate limit category (e.g., "content_generation")
        redis_client: Optional Redis client for distributed rate limiting

    Returns:
        (allowed, info) where info contains remaining quota and retry-after.
    """
    max_requests, window_seconds = RATE_LIMITS.get(endpoint, (100, 60))

    if redis_client:
        return await _check_redis(redis_client, identifier, endpoint, max_requests, window_seconds)
    return _check_memory(identifier, endpoint, max_requests, window_seconds)


def _check_memory(
    identifier: str,
    endpoint: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, dict[str, Any]]:
    """In-memory sliding window rate check."""
    key = f"{identifier}:{endpoint}"
    now = time.time()

    _cleanup_window(key, window_seconds)

    if key not in _windows:
        _windows[key] = []

    current_count = len(_windows[key])

    if current_count >= max_requests:
        oldest = _windows[key][0] if _windows[key] else now
        retry_after = int(window_seconds - (now - oldest)) + 1
        return False, {
            "allowed": False,
            "limit": max_requests,
            "remaining": 0,
            "retry_after": max(1, retry_after),
            "window_seconds": window_seconds,
        }

    _windows[key].append(now)
    return True, {
        "allowed": True,
        "limit": max_requests,
        "remaining": max_requests - current_count - 1,
        "retry_after": 0,
        "window_seconds": window_seconds,
    }


async def _check_redis(
    redis_client: Any,
    identifier: str,
    endpoint: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, dict[str, Any]]:
    """Redis-backed sliding window rate check."""
    key = f"rate_limit:{identifier}:{endpoint}"
    now = time.time()

    try:
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()

        current_count = results[2]

        if current_count > max_requests:
            # Over limit — remove the entry we just added
            await redis_client.zrem(key, str(now))
            earliest = await redis_client.zrange(key, 0, 0, withscores=True)
            retry_after = int(window_seconds - (now - earliest[0][1])) + 1 if earliest else window_seconds
            return False, {
                "allowed": False,
                "limit": max_requests,
                "remaining": 0,
                "retry_after": max(1, retry_after),
                "window_seconds": window_seconds,
            }

        return True, {
            "allowed": True,
            "limit": max_requests,
            "remaining": max_requests - current_count,
            "retry_after": 0,
            "window_seconds": window_seconds,
        }
    except Exception as exc:
        logger.warning("event=redis_rate_limit_failed error=%s fallback=memory", exc)
        return _check_memory(identifier, endpoint, max_requests, window_seconds)


def get_rate_limit_headers(info: dict[str, Any]) -> dict[str, str]:
    """Generate HTTP headers for rate limit responses."""
    headers = {
        "X-RateLimit-Limit": str(info.get("limit", 0)),
        "X-RateLimit-Remaining": str(info.get("remaining", 0)),
    }
    if not info.get("allowed"):
        headers["Retry-After"] = str(info.get("retry_after", 60))
    return headers
