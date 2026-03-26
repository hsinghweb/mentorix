"""
Diagnostic sub-router — diagnostic test generation and submission.

Endpoints:
- POST /start                 — Start onboarding (generate diagnostic)
- POST /diagnostic-questions  — Generate diagnostic MCQs
- POST /submit                — Submit diagnostic test answers
"""
from __future__ import annotations

from fastapi import APIRouter

diagnostic_router = APIRouter(tags=["onboarding:diagnostic"])
