"""
Learning API Package.

Split from the monolithic learning.py into:
- schemas.py  — Pydantic request/response models
- routes.py   — All endpoint handlers and helpers
"""
from app.api.learning.routes import router  # noqa: F401

__all__ = ["router"]
