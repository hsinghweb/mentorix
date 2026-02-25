"""In-memory engagement/disengagement metrics for extended alerts."""
from __future__ import annotations

from collections import deque
from threading import Lock

_DISENGAGEMENT_WINDOW = 50

_lock = Lock()
_recent_disengagements: deque[int] = deque(maxlen=_DISENGAGEMENT_WINDOW)
_total_disengagements = 0


def record_disengagement() -> None:
    """Record one disengagement event (compliance flagged)."""
    with _lock:
        global _total_disengagements
        _total_disengagements += 1
        _recent_disengagements.append(1)


def get_engagement_metrics() -> dict:
    with _lock:
        recent = len(_recent_disengagements)
        total = _total_disengagements
    return {
        "disengagement_recent_count": recent,
        "disengagement_total_count": total,
    }


def reset_engagement_metrics() -> None:
    """Reset (e.g. for tests)."""
    with _lock:
        global _total_disengagements
        _total_disengagements = 0
        _recent_disengagements.clear()
