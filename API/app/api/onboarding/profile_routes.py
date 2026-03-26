"""
Profile sub-router — learner profile, analytics, metrics, and engagement.

Endpoints:
- GET  /profile-history/{learner_id}        — Profile snapshot history
- GET  /where-i-stand/{learner_id}          — Learner standing summary
- GET  /evaluation-analytics/{learner_id}   — Evaluation analytics
- GET  /comparative-analytics/{learner_id}  — Comparative analytics
- GET  /learning-metrics/{learner_id}       — Student learning metrics
- POST /engagement/events                   — Log engagement event
- GET  /engagement/summary/{learner_id}     — Engagement summary
"""
from __future__ import annotations

from fastapi import APIRouter

profile_router = APIRouter(tags=["onboarding:profile"])
