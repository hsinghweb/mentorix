"""In-memory app metrics: request latency and error rates, with optional alerts."""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from starlette.requests import Request
from starlette.responses import Response

# Rolling window size for latency percentiles
_LATENCY_WINDOW = 500
# Alert thresholds
_ERROR_RATE_ALERT_THRESHOLD = 0.10  # 10%
_LATENCY_P95_ALERT_MS = 2000  # 2 seconds

_lock = Lock()
_request_count = 0
_error_count = 0
_latencies: deque[float] = deque(maxlen=_LATENCY_WINDOW)


def record_request(duration_sec: float, is_error: bool) -> None:
    with _lock:
        global _request_count, _error_count
        _request_count += 1
        if is_error:
            _error_count += 1
        _latencies.append(duration_sec)


def get_metrics() -> dict:
    with _lock:
        total = _request_count
        errors = _error_count
        latencies = list(_latencies)

    error_rate = (errors / total) if total else 0.0
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None
    if latencies:
        sorted_ms = sorted(lat * 1000 for lat in latencies)
        n = len(sorted_ms)
        latency_ms_p50 = sorted_ms[int((n - 1) * 0.50)] if n else None
        latency_ms_p95 = sorted_ms[int((n - 1) * 0.95)] if n else None

    alerts: list[str] = []
    if total and error_rate >= _ERROR_RATE_ALERT_THRESHOLD:
        alerts.append("high_error_rate")
    if latency_ms_p95 is not None and latency_ms_p95 >= _LATENCY_P95_ALERT_MS:
        alerts.append("high_latency_p95")

    return {
        "request_count": total,
        "error_count": errors,
        "error_rate": round(error_rate, 4),
        "latency_ms_p50": round(latency_ms_p50, 2) if latency_ms_p50 is not None else None,
        "latency_ms_p95": round(latency_ms_p95, 2) if latency_ms_p95 is not None else None,
        "alerts": alerts,
    }


def reset_metrics() -> None:
    """Reset counters (e.g. for tests)."""
    with _lock:
        global _request_count, _error_count
        _request_count = 0
        _error_count = 0
        _latencies.clear()


async def metrics_middleware(request: Request, call_next) -> Response:
    """Record request duration and status for app metrics (skips /health and /metrics)."""
    path = request.url.path
    if path == "/health" or path.startswith("/metrics"):
        return await call_next(request)
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    record_request(duration, response.status_code >= 400)
    return response
