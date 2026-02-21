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
