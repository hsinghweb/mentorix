"""Admin API: cohort overview and policy violations for operator panel."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.database import get_db
from app.models.entities import Learner, LearnerProfile, PolicyViolation

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cohort")
async def cohort_overview(
    db: AsyncSession = Depends(get_db),
    include_list: bool = Query(False, description="Include learner list"),
    limit: int = Query(50, ge=1, le=500),
):
    """Return learner count and optionally a list of learners (for cohort overview)."""
    count_result = await db.execute(select(func.count(Learner.id)))
    learner_count = count_result.scalar() or 0
    out = {"learner_count": learner_count}
    if include_list and learner_count > 0:
        result = await db.execute(
            select(Learner.id, Learner.name, Learner.grade_level).limit(limit)
        )
        rows = result.all()
        out["learners"] = [
            {"id": str(r.id), "name": r.name, "grade_level": r.grade_level}
            for r in rows
        ]
    return out


@router.get("/policy-violations")
async def list_policy_violations(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    learner_id: UUID | None = Query(None, description="Filter by learner"),
):
    """Return recent policy violations (for compliance panel)."""
    stmt = (
        select(PolicyViolation)
        .order_by(desc(PolicyViolation.created_at))
        .limit(limit)
    )
    if learner_id is not None:
        stmt = stmt.where(PolicyViolation.learner_id == learner_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    out = {
        "total": len(rows),
        "violations": [
            {
                "id": str(v.id),
                "learner_id": str(v.learner_id),
                "policy_code": v.policy_code,
                "chapter": v.chapter,
                "details": v.details,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in rows
        ],
    }
    return out


@router.get("/timeline-drift")
async def timeline_drift_summary(db: AsyncSession = Depends(get_db)):
    """Return aggregate timeline drift (goal vs forecast) across learners with profiles."""
    stmt = select(
        func.count(LearnerProfile.learner_id).label("count"),
        func.avg(LearnerProfile.selected_timeline_weeks).label("avg_selected"),
        func.avg(LearnerProfile.current_forecast_weeks).label("avg_forecast"),
        func.avg(LearnerProfile.timeline_delta_weeks).label("avg_delta"),
    ).where(
        LearnerProfile.selected_timeline_weeks.isnot(None),
        LearnerProfile.current_forecast_weeks.isnot(None),
    )
    result = await db.execute(stmt)
    row = result.one()
    return {
        "learners_with_timeline": row.count or 0,
        "avg_selected_weeks": round(float(row.avg_selected or 0), 1),
        "avg_forecast_weeks": round(float(row.avg_forecast or 0), 1),
        "avg_delta_weeks": round(float(row.avg_delta or 0), 1),
    }
