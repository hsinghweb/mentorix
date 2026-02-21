from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from app.core.event_bus import event_bus
from app.core.settings import settings
from app.runtime.run_manager import run_manager
from app.skills.manager import skill_manager


class ScheduledJob(BaseModel):
    id: str
    name: str
    query: str
    interval_seconds: int = 3600
    enabled: bool = True
    skill_id: str | None = None
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_run_id: str | None = None
    last_status: str | None = None


class SchedulerService:
    def __init__(self):
        self.base_dir = Path(settings.runtime_data_dir)
        self.file = self.base_dir / "scheduled_jobs.json"
        self.jobs: dict[str, ScheduledJob] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def load_jobs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            return
        data = json.loads(self.file.read_text(encoding="utf-8"))
        self.jobs = {item["id"]: ScheduledJob(**item) for item in data}

    def save_jobs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = [job.model_dump() for job in self.jobs.values()]
        self.file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_jobs(self) -> list[ScheduledJob]:
        return list(self.jobs.values())

    def add_job(self, *, name: str, query: str, interval_seconds: int = 3600) -> ScheduledJob:
        skill = skill_manager.match_intent(query)
        job = ScheduledJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            query=query,
            interval_seconds=max(10, int(interval_seconds)),
            skill_id=skill,
            next_run_at=(datetime.utcnow() + timedelta(seconds=max(10, int(interval_seconds)))).isoformat(),
        )
        self.jobs[job.id] = job
        self.save_jobs()
        return job

    def update_job(self, job_id: str, **kwargs) -> ScheduledJob:
        if job_id not in self.jobs:
            raise KeyError(f"job {job_id} not found")
        updated = self.jobs[job_id].model_copy(update=kwargs)
        self.jobs[job_id] = updated
        self.save_jobs()
        return updated

    def delete_job(self, job_id: str) -> None:
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.save_jobs()

    async def trigger_job(self, job_id: str) -> str:
        if job_id not in self.jobs:
            raise KeyError(f"job {job_id} not found")
        return await self._run_job(self.jobs[job_id], forced=True)

    async def _run_job(self, job: ScheduledJob, forced: bool = False) -> str:
        if not forced and not job.enabled:
            return ""
        query = job.query
        skill = skill_manager.get_skill(job.skill_id) if job.skill_id else None
        if skill:
            query = await skill.on_run_start(query)
        await event_bus.publish("scheduler_job_start", "scheduler", {"job_id": job.id, "name": job.name})
        run_id = await run_manager.start_run(query)
        job.last_run_id = run_id
        job.last_run_at = datetime.utcnow().isoformat()
        job.next_run_at = (datetime.utcnow() + timedelta(seconds=job.interval_seconds)).isoformat()
        job.last_status = "started"
        self.jobs[job.id] = job
        self.save_jobs()
        await event_bus.publish("scheduler_job_triggered", "scheduler", {"job_id": job.id, "run_id": run_id})
        return run_id

    async def _tick(self) -> None:
        while self._running:
            now = datetime.utcnow()
            for job in list(self.jobs.values()):
                if not job.enabled:
                    continue
                next_run = datetime.fromisoformat(job.next_run_at) if job.next_run_at else now
                if next_run <= now:
                    try:
                        await self._run_job(job)
                    except Exception as exc:
                        job.last_status = f"failed: {exc}"
                        job.next_run_at = (now + timedelta(seconds=job.interval_seconds)).isoformat()
                        self.jobs[job.id] = job
                        self.save_jobs()
                        await event_bus.publish(
                            "scheduler_job_failed",
                            "scheduler",
                            {"job_id": job.id, "error": str(exc)},
                        )
            await asyncio.sleep(max(1, settings.scheduler_tick_seconds))

    async def start(self) -> None:
        self.load_jobs()
        skill_manager.scan_and_register()
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._tick())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self.save_jobs()


scheduler_service = SchedulerService()
