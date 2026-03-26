"""
Analytics API router — endpoint for outcomes, experiments, and data export.

Provides:
- GET /analytics/outcomes         — Cohort summary
- GET /analytics/outcomes/{id}    — Individual learner outcome
- GET /analytics/export           — CSV export of all outcomes
- GET /analytics/experiments      — A/B experiment results
"""
from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/outcomes")
async def get_cohort_outcomes(db: AsyncSession = Depends(get_db)):
    """Return aggregated cohort outcome metrics."""
    from app.services.outcome_analytics import compute_cohort_summary, cohort_to_dict

    summary = await compute_cohort_summary(db)
    return {"status": "ok", "data": cohort_to_dict(summary)}


@router.get("/outcomes/{learner_id}")
async def get_learner_outcome(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Return outcome metrics for a specific learner."""
    from app.services.outcome_analytics import compute_learner_outcome, outcome_to_dict

    try:
        lid = UUID(learner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid learner_id format")

    outcome = await compute_learner_outcome(db, lid)
    if not outcome:
        raise HTTPException(status_code=404, detail="Learner not found")

    return {"status": "ok", "data": outcome_to_dict(outcome)}


@router.get("/export")
async def export_outcomes_csv(db: AsyncSession = Depends(get_db)):
    """Export all learner outcomes as a CSV file."""
    from app.services.outcome_analytics import (
        compute_learner_outcome,
        outcome_to_dict,
    )
    from app.models.entities import LearnerProfile
    from sqlalchemy import select

    learner_ids = (await db.execute(
        select(LearnerProfile.learner_id)
    )).scalars().all()

    rows = []
    for lid in learner_ids:
        outcome = await compute_learner_outcome(db, lid)
        if outcome:
            rows.append(outcome_to_dict(outcome))

    if not rows:
        return Response(content="No data", media_type="text/plain", status_code=204)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mentorix_outcomes.csv"},
    )


@router.get("/experiments")
async def list_experiments():
    """List all A/B experiments and their status."""
    from app.services.ab_testing import list_experiments as _list

    return {"status": "ok", "experiments": _list()}


@router.get("/experiments/{experiment_id}")
async def get_experiment_results(experiment_id: str):
    """Get detailed results for a specific experiment."""
    from app.services.ab_testing import get_experiment_results as _get

    results = _get(experiment_id)
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])

    return {"status": "ok", "data": results}
