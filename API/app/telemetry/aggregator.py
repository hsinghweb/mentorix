from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.core.settings import settings


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
        for run in runs:
            outcomes[run.get("status", "unknown")] += 1
            for node in run.get("nodes", []):
                total_steps += 1
                retries += int(node.get("retries", 0) or 0)
                agents[node.get("agent", "unknown")] += 1
                if node.get("status") == "failed":
                    failed_steps += 1
        return {
            "total_runs": len(runs),
            "outcomes": dict(outcomes),
            "total_steps": total_steps,
            "failed_steps": failed_steps,
            "step_success_rate": round(((total_steps - failed_steps) / total_steps) * 100, 1) if total_steps else 100.0,
            "total_retries": retries,
            "top_agents": agents.most_common(10),
        }


fleet_telemetry_aggregator = FleetTelemetryAggregator()
