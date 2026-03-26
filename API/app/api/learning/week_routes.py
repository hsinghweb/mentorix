"""
Week sub-router — weekly cycle advancement and task completion.

Endpoints:
- POST /week/advance — Complete current week and advance to next
"""
from __future__ import annotations

from fastapi import APIRouter

week_router = APIRouter(tags=["learning:week"])
