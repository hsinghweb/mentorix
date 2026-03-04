from __future__ import annotations

from threading import Lock

_lock = Lock()
_calls_total = 0
_calls_failed = 0
_calls_fallback = 0
_latency_ms_sum = 0.0


def record_mcp_call(*, latency_ms: float, failed: bool, fallback_used: bool) -> None:
    global _calls_total, _calls_failed, _calls_fallback, _latency_ms_sum
    with _lock:
        _calls_total += 1
        _latency_ms_sum += max(0.0, float(latency_ms))
        if failed:
            _calls_failed += 1
        if fallback_used:
            _calls_fallback += 1


def get_mcp_metrics() -> dict:
    with _lock:
        total = _calls_total
        failed = _calls_failed
        fallback = _calls_fallback
        latency_avg = (_latency_ms_sum / total) if total else 0.0
    return {
        "mcp_calls_total": total,
        "mcp_calls_failed": failed,
        "mcp_fallback_used": fallback,
        "mcp_failure_rate": round((failed / total), 4) if total else 0.0,
        "mcp_latency_ms_avg": round(latency_avg, 2),
    }

