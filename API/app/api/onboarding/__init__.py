"""
Onboarding API Package.

Split from the monolithic onboarding.py into:
- routes.py   — All endpoint handlers and helpers
- (schemas already in app/schemas/onboarding.py)
"""
from app.api.onboarding.routes import router  # noqa: F401
from app.api.onboarding.routes import _build_comparative_analytics  # noqa: F401

__all__ = ["router", "_build_comparative_analytics"]
