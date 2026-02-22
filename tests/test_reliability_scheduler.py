from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import pytest

from app.autonomy.scheduler import SchedulerService
from app.core.settings import settings


@pytest.mark.asyncio
async def test_scheduler_restart_state_recovery(monkeypatch, tmp_path: Path):
    # Isolate scheduler persistence for this test.
    monkeypatch.setattr(settings, "runtime_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "scheduler_tick_seconds", 1)

    async def _start_run_1(_query: str) -> str:
        await asyncio.sleep(0)
        return "run-recovery-1"

    async def _start_run_2(_query: str) -> str:
        await asyncio.sleep(0)
        return "run-recovery-2"

    from app.autonomy import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module.run_manager, "start_run", _start_run_1)
    service = SchedulerService()
    job = service.add_job(name="RecoveryJob", query="run recovery check", interval_seconds=10)
    run_id_1 = await service.trigger_job(job.id)
    assert run_id_1 == "run-recovery-1"
    await service.stop()

    # Simulate process restart with a fresh scheduler instance.
    monkeypatch.setattr(scheduler_module.run_manager, "start_run", _start_run_2)
    restarted = SchedulerService()
    restarted.load_jobs()
    recovered = restarted.jobs.get(job.id)
    assert recovered is not None
    assert recovered.last_run_id == "run-recovery-1"
    assert recovered.last_run_at is not None
    assert recovered.next_run_at is not None

    run_id_2 = await restarted.trigger_job(job.id)
    assert run_id_2 == "run-recovery-2"
    await restarted.stop()


def test_small_local_load_profile_smoke(client):
    # Lightweight local load profile for reliability regression checks.
    health_latencies_ms: list[float] = []
    for _ in range(30):
        t0 = time.perf_counter()
        resp = client.get("/health")
        dt = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 200
        health_latencies_ms.append(dt)

    for _ in range(8):
        learner_id = str(uuid.uuid4())
        start = client.post("/start-session", json={"learner_id": learner_id})
        assert start.status_code == 200

    health_latencies_ms.sort()
    p95_idx = max(0, min(len(health_latencies_ms) - 1, int(len(health_latencies_ms) * 0.95) - 1))
    p95_ms = health_latencies_ms[p95_idx]
    # Keep generous for local machines while still catching major regressions.
    assert p95_ms < 1500.0
