"""
Student outcome analytics — per-learner trajectory reports for research evaluation.

Computes mastery growth rates, chapter completion velocity, diagnostic-to-current
score deltas, and learning trajectory summaries. Exposes data for the admin dashboard
and supports export for research evaluation.

This addresses the V2 audit gap: "No student outcome analytics for research evaluation."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.models.entities import (
    AssessmentResult,
    ChapterProgression,
    LearnerProfile,
    WeeklyPlan,
)

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)


@dataclass
class LearnerOutcome:
    """Aggregated outcome metrics for a single learner."""
    learner_id: str
    name: str
    onboarding_date: datetime | None
    diagnostic_score: float
    current_avg_mastery: float
    mastery_growth_rate: float
    chapters_completed: int
    total_chapters: int
    completion_percentage: float
    avg_test_score: float
    total_assessments: int
    weeks_active: int
    chapters_per_week: float
    diagnostic_to_current_delta: float
    risk_level: str
    trajectory: str  # "improving" | "stable" | "declining"


@dataclass
class CohortSummary:
    """Aggregated metrics across all learners."""
    total_learners: int
    avg_mastery_growth: float
    avg_completion_percentage: float
    avg_diagnostic_score: float
    avg_current_mastery: float
    improving_count: int
    stable_count: int
    declining_count: int
    at_risk_count: int


async def compute_learner_outcome(
    db: AsyncSession,
    learner_id: UUID,
) -> LearnerOutcome | None:
    """Compute outcome metrics for a single learner."""
    try:
        profile = (await db.execute(
            select(LearnerProfile).where(LearnerProfile.learner_id == learner_id)
        )).scalar_one_or_none()
        if not profile:
            return None

        # Chapter progressions
        progressions = (await db.execute(
            select(ChapterProgression).where(ChapterProgression.learner_id == learner_id)
        )).scalars().all()

        completed = [p for p in progressions if str(p.status or "").startswith("completed")]

        # Assessment results
        assessments = (await db.execute(
            select(AssessmentResult).where(AssessmentResult.learner_id == learner_id)
        )).scalars().all()

        # Compute metrics
        diagnostic_score = float(profile.diagnostic_score or 0.0)
        mastery_map = profile.concept_mastery or {}
        current_avg_mastery = (
            sum(mastery_map.values()) / len(mastery_map)
            if mastery_map else 0.0
        )

        total_chapters = 15  # CBSE Class 10 Math
        chapters_completed = len(completed)
        completion_pct = (chapters_completed / total_chapters * 100) if total_chapters > 0 else 0

        avg_test_score = 0.0
        if assessments:
            scores = [float(a.score or 0.0) for a in assessments]
            avg_test_score = sum(scores) / len(scores) if scores else 0.0

        # Weeks active
        onboarding_date = getattr(profile, "onboarding_date", None) or getattr(profile, "created_at", None)
        if onboarding_date:
            days_active = max(1, (datetime.now(timezone.utc) - onboarding_date.replace(tzinfo=timezone.utc if onboarding_date.tzinfo is None else onboarding_date.tzinfo)).days)
            weeks_active = max(1, days_active // 7)
        else:
            weeks_active = 1

        chapters_per_week = chapters_completed / weeks_active if weeks_active > 0 else 0.0

        # Mastery growth
        mastery_delta = current_avg_mastery - diagnostic_score
        growth_rate = mastery_delta / max(1, weeks_active)

        # Trajectory classification
        if mastery_delta > 0.1:
            trajectory = "improving"
        elif mastery_delta < -0.05:
            trajectory = "declining"
        else:
            trajectory = "stable"

        # Risk level
        if current_avg_mastery < 0.4 or (chapters_per_week < 0.5 and completion_pct < 30):
            risk_level = "high"
        elif current_avg_mastery < 0.65 or chapters_per_week < 0.8:
            risk_level = "medium"
        else:
            risk_level = "low"

        return LearnerOutcome(
            learner_id=str(learner_id),
            name=profile.name or "Unknown",
            onboarding_date=onboarding_date,
            diagnostic_score=round(diagnostic_score, 4),
            current_avg_mastery=round(current_avg_mastery, 4),
            mastery_growth_rate=round(growth_rate, 4),
            chapters_completed=chapters_completed,
            total_chapters=total_chapters,
            completion_percentage=round(completion_pct, 1),
            avg_test_score=round(avg_test_score, 4),
            total_assessments=len(assessments),
            weeks_active=weeks_active,
            chapters_per_week=round(chapters_per_week, 2),
            diagnostic_to_current_delta=round(mastery_delta, 4),
            risk_level=risk_level,
            trajectory=trajectory,
        )
    except Exception as exc:
        logger.warning("event=outcome_compute_failed learner=%s error=%s", learner_id, exc)
        return None


async def compute_cohort_summary(db: AsyncSession) -> CohortSummary:
    """Compute aggregated outcome metrics across all learners."""
    learner_ids = (await db.execute(
        select(LearnerProfile.learner_id)
    )).scalars().all()

    outcomes: list[LearnerOutcome] = []
    for lid in learner_ids:
        outcome = await compute_learner_outcome(db, lid)
        if outcome:
            outcomes.append(outcome)

    if not outcomes:
        return CohortSummary(
            total_learners=0, avg_mastery_growth=0, avg_completion_percentage=0,
            avg_diagnostic_score=0, avg_current_mastery=0,
            improving_count=0, stable_count=0, declining_count=0, at_risk_count=0,
        )

    n = len(outcomes)
    return CohortSummary(
        total_learners=n,
        avg_mastery_growth=round(sum(o.mastery_growth_rate for o in outcomes) / n, 4),
        avg_completion_percentage=round(sum(o.completion_percentage for o in outcomes) / n, 1),
        avg_diagnostic_score=round(sum(o.diagnostic_score for o in outcomes) / n, 4),
        avg_current_mastery=round(sum(o.current_avg_mastery for o in outcomes) / n, 4),
        improving_count=sum(1 for o in outcomes if o.trajectory == "improving"),
        stable_count=sum(1 for o in outcomes if o.trajectory == "stable"),
        declining_count=sum(1 for o in outcomes if o.trajectory == "declining"),
        at_risk_count=sum(1 for o in outcomes if o.risk_level == "high"),
    )


def outcome_to_dict(outcome: LearnerOutcome) -> dict[str, Any]:
    """Serialize a LearnerOutcome to a JSON-friendly dict."""
    return {
        "learner_id": outcome.learner_id,
        "name": outcome.name,
        "onboarding_date": outcome.onboarding_date.isoformat() if outcome.onboarding_date else None,
        "diagnostic_score": outcome.diagnostic_score,
        "current_avg_mastery": outcome.current_avg_mastery,
        "mastery_growth_rate": outcome.mastery_growth_rate,
        "chapters_completed": outcome.chapters_completed,
        "total_chapters": outcome.total_chapters,
        "completion_percentage": outcome.completion_percentage,
        "avg_test_score": outcome.avg_test_score,
        "total_assessments": outcome.total_assessments,
        "weeks_active": outcome.weeks_active,
        "chapters_per_week": outcome.chapters_per_week,
        "diagnostic_to_current_delta": outcome.diagnostic_to_current_delta,
        "risk_level": outcome.risk_level,
        "trajectory": outcome.trajectory,
    }


def cohort_to_dict(summary: CohortSummary) -> dict[str, Any]:
    """Serialize a CohortSummary to a JSON-friendly dict."""
    return {
        "total_learners": summary.total_learners,
        "avg_mastery_growth": summary.avg_mastery_growth,
        "avg_completion_percentage": summary.avg_completion_percentage,
        "avg_diagnostic_score": summary.avg_diagnostic_score,
        "avg_current_mastery": summary.avg_current_mastery,
        "improving_count": summary.improving_count,
        "stable_count": summary.stable_count,
        "declining_count": summary.declining_count,
        "at_risk_count": summary.at_risk_count,
        "trajectory_distribution": {
            "improving": summary.improving_count,
            "stable": summary.stable_count,
            "declining": summary.declining_count,
        },
    }
