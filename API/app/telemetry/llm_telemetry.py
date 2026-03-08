"""
LLM Telemetry — per-feature token/cost/error tracking for observability.

Thread-safe in-memory counters exposed via get_llm_telemetry().
Intended to be called by LLM provider wrappers after each generation call.
"""
from __future__ import annotations

from threading import Lock
from typing import Any


_lock = Lock()
_telemetry: dict[str, dict[str, Any]] = {}

# Max allowed retries per generation feature before hard-fail (failure cap)
MAX_RETRIES_PER_FEATURE = 5


def record_llm_call(
    feature: str,
    *,
    tokens: int = 0,
    cost: float = 0.0,
    success: bool = True,
    retries: int = 0,
) -> None:
    with _lock:
        if feature not in _telemetry:
            _telemetry[feature] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
                "errors": 0,
                "retries": 0,
            }
        entry = _telemetry[feature]
        entry["calls"] += 1
        entry["tokens"] += tokens
        entry["cost"] += cost
        entry["retries"] += retries
        if not success:
            entry["errors"] += 1


def get_llm_telemetry() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _telemetry.items()}


def should_fail_open(feature: str) -> bool:
    """Return True if the feature has exceeded its retry budget."""
    with _lock:
        entry = _telemetry.get(feature)
        if not entry:
            return False
        return entry["retries"] >= MAX_RETRIES_PER_FEATURE


def reset() -> None:
    with _lock:
        _telemetry.clear()
