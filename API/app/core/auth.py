from fastapi import HTTPException
from starlette.requests import Request

from app.core.settings import settings


EXEMPT_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


async def api_key_auth_middleware(request: Request, call_next):
    if settings.gateway_auth_enabled:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            provided = request.headers.get("x-api-key", "")
            if not settings.gateway_api_key or provided != settings.gateway_api_key:
                raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing x-api-key")
    return await call_next(request)
