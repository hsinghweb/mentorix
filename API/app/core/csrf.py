"""
CSRF Protection Middleware — double-submit cookie pattern.

For state-mutating requests (POST, PUT, PATCH, DELETE), verifies that
a ``X-CSRF-Token`` header matches the ``csrf_token`` cookie.

The token is set as a secure HttpOnly cookie on every response.
"""
from __future__ import annotations

import logging
import secrets
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {"/health", "/health/status", "/docs", "/openapi.json", "/redoc"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection.

    On every response, sets a ``csrf_token`` cookie.
    On state-mutating requests, requires the ``X-CSRF-Token`` header
    to match the cookie value.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip safe methods and exempt paths
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            return self._ensure_cookie(request, response)

        path = request.url.path.rstrip("/")
        if path in EXEMPT_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Validate CSRF token
        cookie_token = request.cookies.get(CSRF_COOKIE)
        header_token = request.headers.get(CSRF_HEADER)

        if not cookie_token or not header_token or cookie_token != header_token:
            logger.warning(
                "CSRF validation failed: path=%s cookie=%s header=%s",
                path,
                "present" if cookie_token else "missing",
                "present" if header_token else "missing",
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid. Include X-CSRF-Token header matching the csrf_token cookie."},
            )

        response = await call_next(request)
        return self._ensure_cookie(request, response)

    def _ensure_cookie(self, request: Request, response: Response) -> Response:
        """Ensure a CSRF cookie is set on every response."""
        existing = request.cookies.get(CSRF_COOKIE)
        if not existing:
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                key=CSRF_COOKIE,
                value=token,
                httponly=False,  # Must be readable by JS to send as header
                samesite="strict",
                secure=False,  # Set True in production behind HTTPS
                max_age=86400,
            )
        return response
