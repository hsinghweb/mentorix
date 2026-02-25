"""In-memory DB query metrics: duration distribution and p95 for GET /metrics/app."""
from __future__ import annotations

from collections import deque
from threading import Lock

_DB_WINDOW = 500

_lock = Lock()
_durations_sec: deque[float] = deque(maxlen=_DB_WINDOW)


def record_query(duration_sec: float) -> None:
    with _lock:
        _durations_sec.append(max(0.0, float(duration_sec)))


def get_db_metrics() -> dict:
    with _lock:
        values = list(_durations_sec)
    count = len(values)
    if not count:
        return {
            "db_query_count": 0,
            "db_p50_ms": None,
            "db_p95_ms": None,
        }
    sorted_ms = sorted(v * 1000 for v in values)
    n = len(sorted_ms)
    p50 = sorted_ms[int((n - 1) * 0.50)] if n else None
    p95 = sorted_ms[int((n - 1) * 0.95)] if n else None
    return {
        "db_query_count": count,
        "db_p50_ms": round(p50, 2),
        "db_p95_ms": round(p95, 2),
    }


def reset_db_metrics() -> None:
    with _lock:
        _durations_sec.clear()
