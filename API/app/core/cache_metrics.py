"""In-memory Redis cache metrics: hit/miss/set counts and hit ratio."""
from __future__ import annotations

from threading import Lock

_lock = Lock()
_hits = 0
_misses = 0
_sets = 0


def record_cache_get(hit: bool) -> None:
    with _lock:
        global _hits, _misses
        if hit:
            _hits += 1
        else:
            _misses += 1


def record_cache_set() -> None:
    with _lock:
        global _sets
        _sets += 1


def get_cache_metrics() -> dict:
    with _lock:
        hits = _hits
        misses = _misses
        sets = _sets
    total_gets = hits + misses
    hit_ratio = (hits / total_gets) if total_gets else None
    return {
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_sets": sets,
        "cache_get_total": total_gets,
        "cache_hit_ratio": round(hit_ratio, 4) if hit_ratio is not None else None,
    }


def reset_cache_metrics() -> None:
    """Reset counters (e.g. for tests)."""
    with _lock:
        global _hits, _misses, _sets
        _hits = 0
        _misses = 0
        _sets = 0
