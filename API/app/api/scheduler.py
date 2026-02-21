from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.autonomy.scheduler import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/jobs")
async def list_jobs():
    return {"jobs": [job.model_dump() for job in scheduler_service.list_jobs()]}


@router.post("/jobs")
async def create_job(payload: dict):
    try:
        job = scheduler_service.add_job(
            name=payload["name"],
            query=payload["query"],
            interval_seconds=int(payload.get("interval_seconds", 3600)),
        )
        return job.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"missing field {exc}") from exc


@router.patch("/jobs/{job_id}")
async def update_job(job_id: str, payload: dict):
    try:
        job = scheduler_service.update_job(job_id, **payload)
        return job.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    scheduler_service.delete_job(job_id)
    return {"deleted": True}


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str):
    try:
        run_id = await scheduler_service.trigger_job(job_id)
        return {"job_id": job_id, "run_id": run_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
