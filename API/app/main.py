from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.core.bootstrap import initialize_database
from app.core.logging import configure_logging
from app.core.settings import settings
from app.memory.database import SessionLocal, engine


configure_logging(settings.log_level)

app = FastAPI(title="Mentorix API", version="0.1.0")
app.include_router(health_router)
app.include_router(sessions_router)


@app.on_event("startup")
async def on_startup():
    async with SessionLocal() as session:
        await initialize_database(session, engine)