"""
Content sub-router — reading material generation, section content, and source retrieval.

Endpoints:
- POST /content           — Generate chapter reading content
- POST /content/section   — Generate subsection reading content
- POST /reading/complete  — Mark reading as complete
- POST /test/question/explain — Explain a test question
- GET  /chapter/{n}/sections/{learner_id} — List chapter sections
- GET  /source-section/{n}/{section_id}   — Get source section text
- GET  /source-chapter/{n}                — Get source chapter text
"""
from __future__ import annotations

from fastapi import APIRouter

# Sub-router registered under the /learning prefix by the aggregator.
content_router = APIRouter(tags=["learning:content"])

# Endpoints are defined in the main routes.py and mounted here.
# This module exists to establish the sub-router boundary for future
# gradual migration of endpoint logic out of the monolithic routes.py.
