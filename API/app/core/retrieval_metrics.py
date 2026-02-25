"""In-memory RAG retrieval quality metrics: confidence distribution (relevance proxy)."""
from __future__ import annotations

from collections import deque
from threading import Lock

# Rolling window for recent retrieval confidences
_RETRIEVAL_WINDOW = 200
_LOW_CONFIDENCE_THRESHOLD = 0.35

_lock = Lock()
_confidences: deque[float] = deque(maxlen=_RETRIEVAL_WINDOW)


def record_retrieval(confidence: float) -> None:
    """Record one RAG retrieval confidence (0–1)."""
    c = max(0.0, min(1.0, float(confidence)))
    with _lock:
        _confidences.append(c)


def get_retrieval_metrics() -> dict:
    with _lock:
        values = list(_confidences)
    count = len(values)
    if not count:
        return {
            "retrieval_count": 0,
            "retrieval_avg_confidence": None,
            "retrieval_low_confidence_count": 0,
            "retrieval_low_confidence_ratio": None,
        }
    avg = sum(values) / count
    low_count = sum(1 for v in values if v < _LOW_CONFIDENCE_THRESHOLD)
    low_ratio = low_count / count
    return {
        "retrieval_count": count,
        "retrieval_avg_confidence": round(avg, 4),
        "retrieval_low_confidence_count": low_count,
        "retrieval_low_confidence_ratio": round(low_ratio, 4),
    }


def reset_retrieval_metrics() -> None:
    """Reset (e.g. for tests)."""
    with _lock:
        _confidences.clear()
