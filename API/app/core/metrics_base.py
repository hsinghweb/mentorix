"""
Metrics Base — Shared pattern for all domain-specific metrics collectors.

Consolidates the common interface used by:
  app_metrics, cache_metrics, db_metrics, engagement_metrics,
  mcp_metrics, retrieval_metrics

Each domain module should subclass ``MetricsCollector`` to inherit
the shared counter/gauge/histogram pattern and the ``snapshot()`` method
used by the ``/health/status`` and admin endpoints.
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """
    Base class for domain-specific metrics collectors.

    Provides thread-safe counters, gauges, and histograms with a
    unified ``snapshot()`` output format.
    """

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._created_at = time.time()

    # ── Counters ─────────────────────────────────────────────────────

    def inc(self, name: str, value: int = 1) -> None:
        """Increment a named counter."""
        with self._lock:
            self._counters[name] += value

    def counter(self, name: str) -> int:
        """Read a counter value."""
        with self._lock:
            return self._counters.get(name, 0)

    # ── Gauges ───────────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge to a specific value."""
        with self._lock:
            self._gauges[name] = value

    def gauge(self, name: str) -> float:
        """Read a gauge value."""
        with self._lock:
            return self._gauges.get(name, 0.0)

    # ── Histograms ───────────────────────────────────────────────────

    def observe(self, name: str, value: float, max_samples: int = 100) -> None:
        """Record an observation in a histogram (capped ring buffer)."""
        with self._lock:
            h = self._histograms[name]
            h.append(value)
            if len(h) > max_samples:
                self._histograms[name] = h[-max_samples:]

    def histogram_stats(self, name: str) -> dict[str, float]:
        """Return count, sum, avg, min, max for a histogram."""
        with self._lock:
            values = list(self._histograms.get(name, []))
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(values),
            "sum": round(sum(values), 4),
            "avg": round(sum(values) / len(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
        }

    # ── Snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of all metrics for this domain."""
        with self._lock:
            return {
                "domain": self.domain,
                "uptime_seconds": round(time.time() - self._created_at, 1),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.histogram_stats(name)
                    for name in self._histograms
                },
            }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# ── Global registry ──────────────────────────────────────────────────

_registry: dict[str, MetricsCollector] = {}


def get_collector(domain: str) -> MetricsCollector:
    """Get or create a metrics collector for the given domain."""
    if domain not in _registry:
        _registry[domain] = MetricsCollector(domain)
    return _registry[domain]


def all_snapshots() -> dict[str, dict[str, Any]]:
    """Return snapshots for every registered domain collector."""
    return {name: collector.snapshot() for name, collector in sorted(_registry.items())}
