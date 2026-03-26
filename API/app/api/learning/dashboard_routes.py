"""
Dashboard sub-router — dashboard view, analytics, confidence trends, decisions.

Endpoints:
- GET /dashboard/{learner_id}         — Student dashboard
- GET /plan-history/{learner_id}      — Plan revision history
- GET /confidence-trend/{learner_id}  — Mastery confidence trend data
- GET /decisions/{learner_id}         — Agent decision log
"""
from __future__ import annotations

from fastapi import APIRouter

dashboard_router = APIRouter(tags=["learning:dashboard"])
