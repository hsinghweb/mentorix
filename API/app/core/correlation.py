"""
Correlation ID middleware — attaches a unique request-scoped correlation ID
to every request/response for end-to-end traceability across logs.

The ID is read from the ``X-Correlation-ID`` header if provided (e.g. by an
API gateway), otherwise a new UUID4 is generated. The ID is:
  - stored in request.state for access by downstream handlers
  - returned in the ``X-Correlation-ID`` response header
  - injected into the logging context via a LogRecord filter
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Context variable holding the current correlation ID (request-scoped).
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

HEADER_NAME = "X-Correlation-ID"


class CorrelationIdMiddleware:
    """
    ASGI middleware that extracts or generates a correlation ID per request.

    Usage in main.py::

        from app.core.correlation import CorrelationIdMiddleware
        app.add_middleware(CorrelationIdMiddleware)
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        header_key = HEADER_NAME.lower().encode()
        cid = headers.get(header_key, b"").decode() or str(uuid.uuid4())

        # Store in context variable for logging and downstream use
        token = correlation_id_var.set(cid)

        async def send_with_cid(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((HEADER_NAME.encode(), cid.encode()))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_cid)
        finally:
            correlation_id_var.reset(token)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that injects ``correlation_id`` into every LogRecord.

    Usage::

        handler = logging.StreamHandler()
        handler.addFilter(CorrelationIdFilter())
        formatter = logging.Formatter(
            '%(levelname)s %(correlation_id)s %(message)s'
        )
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("")  # type: ignore[attr-defined]
        return True


def get_correlation_id() -> str:
    """Return the current request's correlation ID (empty string if none)."""
    return correlation_id_var.get("")
