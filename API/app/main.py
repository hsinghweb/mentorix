import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.grounding import router as grounding_router
from app.api.learning import router as learning_router
from app.api.onboarding import router as onboarding_router
from app.api.metrics import router as metrics_router
from app.api.scheduler import router as scheduler_router
from app.autonomy.scheduler import scheduler_service
from app.core.auth import api_key_auth_middleware
from app.core.bootstrap import initialize_database
from app.core.app_metrics import metrics_middleware
from app.core.errors import (
    http_exception_handler,
    input_length_guard_middleware,
    rate_limit_middleware,
    request_id_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.settings import settings
from app.memory.database import SessionLocal, engine
from app.mcp.providers import register_default_mcp_providers
from app.rag.grounding_ingest import ensure_grounding_ready, run_grounding_ingestion
from app.runtime.persistence import snapshot_persistence
from app.core.config_governance import validate_all as validate_config
from fastapi import HTTPException


configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mentorix API", version="0.1.0")
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(scheduler_router)
app.include_router(metrics_router)
app.include_router(grounding_router)
app.include_router(admin_router)
app.include_router(onboarding_router)
app.include_router(learning_router)
app.middleware("http")(api_key_auth_middleware)
app.middleware("http")(request_id_middleware)
app.middleware("http")(metrics_middleware)
app.middleware("http")(input_length_guard_middleware)
app.middleware("http")(rate_limit_middleware)
# CORS: restrict origins in non-dev environments
_cors_origins = ["*"] if settings.app_env == "dev" else [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.on_event("startup")
async def on_startup():
    # Config governance: validate model registry + critical settings
    drift_errors = validate_config(fail_fast=False)
    if drift_errors:
        logger.warning("Config drift detected (%d issues) — check logs above", len(drift_errors))
    register_default_mcp_providers()
    async with SessionLocal() as session:
        await initialize_database(session, engine)
        if settings.grounding_prepare_on_start:
            summary = await run_grounding_ingestion(session)
            logger.info("Grounding ingestion startup summary: %s", summary)
        if settings.grounding_require_ready:
            ready, detail = await ensure_grounding_ready(session)
            if not ready:
                raise RuntimeError(f"Grounding validation failed: {detail}")
    snapshot_persistence.load_snapshot()
    if settings.scheduler_enabled:
        await scheduler_service.start()


@app.on_event("shutdown")
async def on_shutdown():
    snapshot_persistence.save_snapshot()
    if settings.scheduler_enabled:
        await scheduler_service.stop()
