"""
Error-Rate Tracker — sliding-window error rate tracking per provider/module
with fallback routing integration.

Works alongside the existing CircuitBreaker in resilience.py to provide
per-module error visibility and automatic fallback when primary provider is degraded.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any


_lock = Lock()

# Sliding window: each entry is (timestamp, success_bool)
_windows: dict[str, deque[tuple[float, bool]]] = {}
_WINDOW_SIZE = 100
_WINDOW_TTL_SECONDS = 300  # 5 minutes


def record(module: str, success: bool) -> None:
    """Record a success/failure for a given module."""
    with _lock:
        if module not in _windows:
            _windows[module] = deque(maxlen=_WINDOW_SIZE)
        _windows[module].append((time.time(), success))


def get_error_rate(module: str) -> float:
    """Return the error rate for a module within the sliding window (0.0-1.0)."""
    with _lock:
        window = _windows.get(module)
        if not window:
            return 0.0
        cutoff = time.time() - _WINDOW_TTL_SECONDS
        recent = [(ts, ok) for ts, ok in window if ts >= cutoff]
        if not recent:
            return 0.0
        errors = sum(1 for _, ok in recent if not ok)
        return errors / len(recent)


def get_all_rates() -> dict[str, dict[str, Any]]:
    """Return error rates for all tracked modules."""
    with _lock:
        result = {}
        cutoff = time.time() - _WINDOW_TTL_SECONDS
        for module, window in _windows.items():
            recent = [(ts, ok) for ts, ok in window if ts >= cutoff]
            total = len(recent)
            errors = sum(1 for _, ok in recent if not ok)
            result[module] = {
                "total_calls": total,
                "errors": errors,
                "error_rate": round(errors / total, 4) if total else 0.0,
            }
        return result


def should_fallback(module: str, threshold: float = 0.5) -> bool:
    """Return True if the module's error rate exceeds the fallback threshold."""
    return get_error_rate(module) > threshold


def get_fallback_provider(primary_module: str) -> str | None:
    """
    Determine which fallback provider to use when primary is degraded.

    Fallback strategy:
      - gemini-based modules → try ollama equivalent
      - ollama-based modules → no fallback (return None)
    """
    if "gemini" in primary_module.lower():
        return primary_module.replace("gemini", "ollama")
    return None


def reset() -> None:
    with _lock:
        _windows.clear()
