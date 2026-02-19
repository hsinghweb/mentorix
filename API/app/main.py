from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import settings


configure_logging(settings.log_level)

app = FastAPI(title="Mentorix API", version="0.1.0")
app.include_router(health_router)
