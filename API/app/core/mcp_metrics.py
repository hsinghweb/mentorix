from __future__ import annotations

from threading import Lock

_lock = Lock()
_calls_total = 0
_calls_failed = 0
_calls_fallback = 0
_latency_ms_sum = 0.0
_by_operation: dict[str, dict[str, float]] = {}


def record_mcp_call(*, operation: str, latency_ms: float, failed: bool, fallback_used: bool) -> None:
    global _calls_total, _calls_failed, _calls_fallback, _latency_ms_sum, _by_operation
    with _lock:
        _calls_total += 1
        _latency_ms_sum += max(0.0, float(latency_ms))
        if failed:
            _calls_failed += 1
        if fallback_used:
            _calls_fallback += 1
        bucket = _by_operation.setdefault(
            str(operation or "unknown"),
            {"total": 0.0, "failed": 0.0, "fallback": 0.0, "latency_sum": 0.0},
        )
        bucket["total"] += 1
        bucket["latency_sum"] += max(0.0, float(latency_ms))
        if failed:
            bucket["failed"] += 1
        if fallback_used:
            bucket["fallback"] += 1


def get_mcp_metrics() -> dict:
    with _lock:
        total = _calls_total
        failed = _calls_failed
        fallback = _calls_fallback
        latency_avg = (_latency_ms_sum / total) if total else 0.0
        by_operation = []
        for operation, stats in sorted(_by_operation.items(), key=lambda item: item[0]):
            op_total = int(stats["total"])
            op_failed = int(stats["failed"])
            op_fallback = int(stats["fallback"])
            op_latency_avg = (float(stats["latency_sum"]) / op_total) if op_total else 0.0
            by_operation.append(
                {
                    "operation": operation,
                    "calls_total": op_total,
                    "calls_failed": op_failed,
                    "fallback_used": op_fallback,
                    "failure_rate": round((op_failed / op_total), 4) if op_total else 0.0,
                    "fallback_rate": round((op_fallback / op_total), 4) if op_total else 0.0,
                    "latency_ms_avg": round(op_latency_avg, 2),
                }
            )
    return {
        "mcp_calls_total": total,
        "mcp_calls_failed": failed,
        "mcp_fallback_used": fallback,
        "mcp_failure_rate": round((failed / total), 4) if total else 0.0,
        "mcp_fallback_rate": round((fallback / total), 4) if total else 0.0,
        "mcp_latency_ms_avg": round(latency_avg, 2),
        "mcp_by_operation": by_operation,
    }

