from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.events import router as events_router
from app.api.memory import router as memory_router
from app.api.metrics import router as metrics_router
from app.api.notifications import router as notifications_router
from app.api.runs import router as runs_router
from app.api.scheduler import router as scheduler_router
from app.api.sessions import router as sessions_router
from app.autonomy.scheduler import scheduler_service
from app.core.auth import api_key_auth_middleware
from app.core.bootstrap import initialize_database
from app.core.errors import (
    http_exception_handler,
    request_id_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.settings import settings
from app.memory.database import SessionLocal, engine
from app.runtime.persistence import snapshot_persistence
from fastapi import HTTPException


configure_logging(settings.log_level)

app = FastAPI(title="Mentorix API", version="0.1.0")
app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(runs_router)
app.include_router(events_router)
app.include_router(scheduler_router)
app.include_router(memory_router)
app.include_router(metrics_router)
app.include_router(notifications_router)
app.middleware("http")(api_key_auth_middleware)
app.middleware("http")(request_id_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.on_event("startup")
async def on_startup():
    async with SessionLocal() as session:
        await initialize_database(session, engine)
    snapshot_persistence.load_snapshot()
    if settings.scheduler_enabled:
        await scheduler_service.start()


@app.on_event("shutdown")
async def on_shutdown():
    snapshot_persistence.save_snapshot()
    if settings.scheduler_enabled:
        await scheduler_service.stop()