"""
Learner State Profile — computes interpretable profile signals from existing
student journey data (session logs, assessment results, engagement events).

Provides simplified labels for the student UI and detailed metrics for admin UI.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssessmentResult, EngagementEvent, SessionLog

logger = logging.getLogger(__name__)

# ── Threshold constants ────────────────────────────────────────────────────
# Weights for computing derived signals
MOTIVATION_ENGAGEMENT_WEIGHT = 0.5
"""Contribution of engagement score towards motivation index."""
MOTIVATION_CONSISTENCY_WEIGHT = 0.5
"""Contribution of consistency towards motivation index."""

CONFUSION_ERROR_WEIGHT = 0.6
"""Contribution of error rate towards confusion risk."""
CONFUSION_MOTIVATION_WEIGHT = 0.4
"""Contribution of (inverted) motivation towards confusion risk."""

CONFIDENCE_ACCURACY_WEIGHT = 0.40
"""Contribution of accuracy (1 - error_rate) towards confidence metric."""
CONFIDENCE_MOTIVATION_WEIGHT = 0.30
"""Contribution of motivation towards confidence metric."""
CONFIDENCE_CONSISTENCY_WEIGHT = 0.30
"""Contribution of consistency towards confidence metric."""

# Label boundaries
STATUS_RISK_THRESHOLD = 0.4
"""Confusion risk below this → 'On Track'; at/above → 'Needs Review'."""
PACE_FAST_THRESHOLD = 0.7
"""Pace above this → 'Fast'."""
PACE_STEADY_THRESHOLD = 0.4
"""Pace at/above this (and ≤ FAST) → 'Steady'; below → 'Needs Attention'."""
MOTIVATION_HIGH_THRESHOLD = 0.7
"""Motivation at/above this → 'High'."""
MOTIVATION_MODERATE_THRESHOLD = 0.4
"""Motivation at/above this (and < HIGH) → 'Moderate'; below → 'Low'."""

ACTIVE_DAYS_TARGET = 5.0
"""Expected active days per week for full consistency score."""


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


async def compute_learner_state_profile(
    session: AsyncSession,
    learner_id: str,
    *,
    window_days: int = 30,
) -> dict[str, Any]:
    """
    Compute an interpretable profile snapshot for a learner using existing DB signals.

    Returns dict with:
      - motivation, consistency, confusion_risk, pace, confidence (0-1 floats)
      - student_labels  (simplified for student UI)
      - admin_metrics   (detailed for admin UI)
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    lid = str(learner_id)

    # --- Engagement: count distinct active days ---
    active_days_q = select(
        func.count(func.distinct(func.date(EngagementEvent.created_at)))
    ).where(
        EngagementEvent.learner_id == lid,
        EngagementEvent.created_at >= window_start,
    )
    active_days_result = await session.execute(active_days_q)
    active_days = int(active_days_result.scalar_one_or_none() or 0)

    total_weeks = max(1, window_days / 7)
    days_per_week = active_days / total_weeks
    consistency = _clamp(days_per_week / ACTIVE_DAYS_TARGET)

    # --- Engagement score from event count ---
    event_count_q = select(func.count()).where(
        EngagementEvent.learner_id == lid,
        EngagementEvent.created_at >= window_start,
    )
    event_count_result = await session.execute(event_count_q)
    event_count = int(event_count_result.scalar_one_or_none() or 0)
    engagement_score = _clamp(event_count / max(1, window_days))

    motivation = _clamp(
        (engagement_score * MOTIVATION_ENGAGEMENT_WEIGHT)
        + (consistency * MOTIVATION_CONSISTENCY_WEIGHT)
    )

    # --- Assessment error rate ---
    assessment_q = select(
        func.count(),
        func.count().filter(AssessmentResult.is_correct == False),  # noqa: E712
    ).where(
        AssessmentResult.learner_id == lid,
        AssessmentResult.timestamp >= window_start,
    )
    try:
        assess_result = await session.execute(assessment_q)
        row = assess_result.one()
        total_assessments = int(row[0] or 0)
        wrong_answers = int(row[1] or 0)
    except Exception:
        logger.warning("Assessment query failed for learner %s, defaulting to zero", lid)
        total_assessments = 0
        wrong_answers = 0

    error_rate = wrong_answers / max(1, total_assessments)

    # --- Session pace (average adaptation_score from session logs) ---
    pace_q = select(func.avg(SessionLog.adaptation_score)).where(
        SessionLog.learner_id == lid,
        SessionLog.timestamp >= window_start,
    )
    pace_result = await session.execute(pace_q)
    avg_adaptation = float(pace_result.scalar_one_or_none() or 0.5)

    # --- Derived signals ---
    confusion_risk = _clamp(
        (error_rate * CONFUSION_ERROR_WEIGHT)
        + ((1.0 - motivation) * CONFUSION_MOTIVATION_WEIGHT)
    )
    pace = _clamp(avg_adaptation)
    confidence = _clamp(
        CONFIDENCE_ACCURACY_WEIGHT * (1 - error_rate)
        + CONFIDENCE_MOTIVATION_WEIGHT * motivation
        + CONFIDENCE_CONSISTENCY_WEIGHT * consistency
    )

    # --- Student UI labels ---
    student_labels = {
        "status": "On Track" if confusion_risk < STATUS_RISK_THRESHOLD else "Needs Review",
        "pace_label": (
            "Fast"
            if pace > PACE_FAST_THRESHOLD
            else ("Steady" if pace >= PACE_STEADY_THRESHOLD else "Needs Attention")
        ),
        "motivation_label": (
            "High"
            if motivation >= MOTIVATION_HIGH_THRESHOLD
            else (
                "Moderate"
                if motivation >= MOTIVATION_MODERATE_THRESHOLD
                else "Low"
            )
        ),
    }

    # --- Admin detailed metrics ---
    admin_metrics = {
        "motivation_index": round(motivation, 3),
        "consistency_index": round(consistency, 3),
        "confusion_risk_score": round(confusion_risk, 3),
        "pace_index": round(pace, 3),
        "confidence_metric": round(confidence, 3),
        "error_rate": round(error_rate, 3),
        "active_days": active_days,
        "total_assessments": total_assessments,
        "window_days": window_days,
    }

    return {
        "learner_id": lid,
        "motivation": round(motivation, 3),
        "consistency": round(consistency, 3),
        "confusion_risk": round(confusion_risk, 3),
        "pace": round(pace, 3),
        "confidence": round(confidence, 3),
        "student_labels": student_labels,
        "admin_metrics": admin_metrics,
    }
