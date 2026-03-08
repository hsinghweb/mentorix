import logging
import uuid

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details=None,
) -> JSONResponse:
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(request),
            "details": details,
        },
    }
    return JSONResponse(status_code=status_code, content=payload)


async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(
        request,
        code="http_error",
        message=str(exc.detail),
        status_code=exc.status_code,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        request,
        code="validation_error",
        message="Request validation failed",
        status_code=422,
        details=exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception | request_id=%s", get_request_id(request), exc_info=exc)
    return error_response(
        request,
        code="internal_error",
        message="Internal server error",
        status_code=500,
    )


async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id")
    request.state.request_id = incoming or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response


# ── Input Length Guard ──────────────────────────────────────────────────────
MAX_BODY_SIZE = 512_000  # 500 KB

async def input_length_guard_middleware(request: Request, call_next):
    """Reject request bodies larger than MAX_BODY_SIZE bytes."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"success": False, "error": {"code": "payload_too_large", "message": f"Request body exceeds {MAX_BODY_SIZE} bytes"}},
        )
    return await call_next(request)


# ── Rate Limiting (auth endpoints) ──────────────────────────────────────────
import time as _time
from collections import defaultdict

_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10  # requests per window
RATE_LIMITED_PATHS = {"/auth/login", "/auth/signup", "/auth/admin-login"}

async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory rate limiter for auth endpoints."""
    if request.url.path in RATE_LIMITED_PATHS:
        client_ip = request.client.host if request.client else "unknown"
        now = _time.time()
        # Prune old entries
        _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(_rate_store[client_ip]) >= RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": {"code": "rate_limited", "message": "Too many requests. Try again later."}},
            )
        _rate_store[client_ip].append(now)
    return await call_next(request)

