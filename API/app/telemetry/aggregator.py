from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.core.settings import settings


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _run_duration_sec(run: dict) -> float | None:
    created = _parse_iso(run.get("created_at"))
    updated = _parse_iso(run.get("updated_at"))
    if created and updated:
        delta = updated - created
        return max(0.0, delta.total_seconds())
    return None


class FleetTelemetryAggregator:
    def __init__(self):
        self.runs_dir = Path(settings.runtime_data_dir) / "runs"

    def _scan_runs(self) -> list[dict]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for file in self.runs_dir.glob("run_*.json"):
            try:
                runs.append(json.loads(file.read_text(encoding="utf-8")))
            except Exception:
                continue
        return runs

    def aggregate(self) -> dict:
        runs = self._scan_runs()
        outcomes = Counter()
        retries = 0
        total_steps = 0
        failed_steps = 0
        agents = Counter()
        run_durations: list[float] = []
        for run in runs:
            outcomes[run.get("status", "unknown")] += 1
            dur = _run_duration_sec(run)
            if dur is not None:
                run_durations.append(dur)
            for node in run.get("nodes", []):
                total_steps += 1
                retries += int(node.get("retries", 0) or 0)
                agents[node.get("agent", "unknown")] += 1
                if node.get("status") == "failed":
                    failed_steps += 1
        run_durations.sort()
        n = len(run_durations)
        p95_duration_sec = run_durations[int((n - 1) * 0.95)] if n else None
        max_duration_sec = run_durations[-1] if n else None
        return {
            "total_runs": len(runs),
            "outcomes": dict(outcomes),
            "total_steps": total_steps,
            "failed_steps": failed_steps,
            "step_success_rate": round(((total_steps - failed_steps) / total_steps) * 100, 1) if total_steps else 100.0,
            "total_retries": retries,
            "top_agents": agents.most_common(10),
            "max_run_duration_sec": round(max_duration_sec, 2) if max_duration_sec is not None else None,
            "p95_run_duration_sec": round(p95_duration_sec, 2) if p95_duration_sec is not None else None,
        }


fleet_telemetry_aggregator = FleetTelemetryAggregator()
