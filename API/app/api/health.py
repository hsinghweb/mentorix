from fastapi import APIRouter

from app.autonomy.scheduler import scheduler_service
from app.core.settings import settings
from app.runtime.run_manager import run_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mentorix-api",
        "active_runs": len(run_manager.list_runs()),
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduled_jobs": len(scheduler_service.list_jobs()),
    }
