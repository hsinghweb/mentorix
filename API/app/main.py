from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
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
from fastapi import HTTPException


configure_logging(settings.log_level)

app = FastAPI(title="Mentorix API", version="0.1.0")
app.include_router(health_router)
app.include_router(sessions_router)
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