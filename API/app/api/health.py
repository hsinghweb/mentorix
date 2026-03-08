from fastapi import APIRouter

from app.autonomy.scheduler import scheduler_service
from app.core.resilience import get_breakers_status
from app.core.settings import settings
from app.memory.store import get_memory_runtime_status
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


@router.get("/health/status")
async def system_status():
    """
    Comprehensive system status covering backend, LLM, embeddings,
    memory, and circuit breaker states.  No secrets exposed.
    """
    breakers = get_breakers_status()
    memory_status = get_memory_runtime_status()

    # LLM provider readiness
    llm_status = {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_key_configured": bool(settings.gemini_api_key),
    }

    # Embedding provider readiness
    embedding_status = {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
    }

    # Determine overall health
    has_open_breaker = any(
        b.get("state") == "open" for b in breakers.values()
    )
    overall = "degraded" if has_open_breaker else "healthy"

    return {
        "overall": overall,
        "llm": llm_status,
        "embedding": embedding_status,
        "memory": memory_status,
        "circuit_breakers": breakers,
        "scheduler_enabled": settings.scheduler_enabled,
        "active_runs": len(run_manager.list_runs()),
    }

