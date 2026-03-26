"""
Test sub-router — test generation, submission, and section tests.

Endpoints:
- POST /test/generate          — Generate chapter-final test
- POST /test/submit            — Submit chapter-final test answers
- POST /test/section/generate  — Generate section-level test
"""
from __future__ import annotations

from fastapi import APIRouter

test_router = APIRouter(tags=["learning:test"])
