"""
Plan sub-router — weekly plan management, replanning, and versioning.

Endpoints:
- GET  /plan/{learner_id}         — Get current weekly plan
- POST /weekly-replan             — Trigger weekly replan
- GET  /plan-versions/{learner_id} — Plan version history
- GET  /forecast-history/{learner_id} — Forecast history
- GET  /daily-plan/{learner_id}   — Daily plan view
"""
from __future__ import annotations

from fastapi import APIRouter

plan_router = APIRouter(tags=["onboarding:plan"])
