"""
Agent orchestration bridge — lightweight dispatch to agents from route handlers.

This module bridges the gap between the route handlers (which contain the
main user journey logic) and the agent classes (which provide enriched
logic for assessment grading, onboarding analysis, and post-test reflection).

Each ``dispatch_*`` function is fire-and-forget safe: failures are logged
but never propagate to the caller.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.agents.agent_interface import AgentContext
from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)


# ── Assessment Dispatch ────────────────────────────────────────────────

async def dispatch_assessment(
    learner_id: str,
    chapter: str,
    section_id: str | None,
    score: float,
    correct: int,
    total: int,
    question_results: list[dict],
) -> dict[str, Any] | None:
    """
    Dispatch assessment grading to AssessmentAgent for enriched evaluation.

    Returns the agent's evaluation dict or *None* if the agent is unavailable.
    The route handler uses its own scoring as the source of truth; the agent
    evaluation supplements it with error classification and feedback.
    """
    try:
        from app.agents.assessment import AssessmentAgent

        agent = AssessmentAgent()
        context = AgentContext(
            learner_id=UUID(learner_id) if isinstance(learner_id, str) else learner_id,
            chapter=chapter,
            extra={
                "section_id": section_id,
                "score": score,
                "correct": correct,
                "total": total,
                "question_results": question_results,
                "question": f"Chapter test: {chapter}",
                "student_answer": f"Scored {correct}/{total}",
                "expected_answer": f"Pass threshold",
            },
        )
        result = await agent.run(context)
        logger.info(
            "event=agent_dispatch agent=assessment learner=%s chapter=%s score=%.2f decision=%s",
            learner_id, chapter, score, result.decision,
        )
        return result.to_dict() if result.success else None
    except Exception as exc:
        logger.warning(
            "event=agent_dispatch_failed agent=assessment learner=%s error=%s",
            learner_id, exc,
        )
        return None


# ── Reflection Dispatch ────────────────────────────────────────────────

async def dispatch_reflection(
    learner_id: str,
    chapter: str,
    score: float,
    passed: bool,
    attempt_number: int,
    decision: str,
) -> dict[str, Any] | None:
    """
    Dispatch post-test reflection to ReflectionAgent.

    Returns the agent's reflection dict (recommendation, mastery_trend, etc.)
    or *None* if the agent is unavailable.
    """
    try:
        from app.agents.reflection import ReflectionAgent

        agent = ReflectionAgent()
        context = AgentContext(
            learner_id=UUID(learner_id) if isinstance(learner_id, str) else learner_id,
            chapter=chapter,
            extra={
                "concept": chapter,
                "current_score": score,
                "mastery_map": {},
                "engagement_score": 0.5,
                "retention_decay": 0.1,
                "assessment_count": attempt_number,
                "passed": passed,
                "decision": decision,
            },
        )
        result = await agent.run(context)
        logger.info(
            "event=agent_dispatch agent=reflection learner=%s recommendation=%s",
            learner_id,
            result.data.get("recommendation", "unknown") if result.success else "none",
        )
        return result.to_dict() if result.success else None
    except Exception as exc:
        logger.warning(
            "event=agent_dispatch_failed agent=reflection learner=%s error=%s",
            learner_id, exc,
        )
        return None


# ── Onboarding Dispatch ───────────────────────────────────────────────

async def dispatch_onboarding_analysis(
    learner_id: str,
    diagnostic_results: list[dict],
    overall_score: float,
) -> dict[str, Any] | None:
    """
    Dispatch diagnostic analysis to OnboardingAgent.

    Returns the agent's analysis dict (risk_level, recommended_pace, etc.)
    or *None* if the agent is unavailable.
    """
    try:
        from app.agents.onboarding import OnboardingAgent

        agent = OnboardingAgent()
        # Build mastery map from diagnostic results
        mastery_map = {}
        for dr in diagnostic_results:
            ch = dr.get("chapter", dr.get("chapter_name", "unknown"))
            sc = dr.get("score", dr.get("mastery", 0.0))
            mastery_map[ch] = float(sc)

        context = AgentContext(
            learner_id=UUID(learner_id) if isinstance(learner_id, str) else learner_id,
            extra={
                "mastery_map": mastery_map,
                "diagnostic_score": overall_score,
                "selected_timeline_weeks": 16,
            },
        )
        result = await agent.run(context)
        logger.info(
            "event=agent_dispatch agent=onboarding learner=%s risk=%s",
            learner_id,
            result.data.get("risk_level", "unknown") if result.success else "none",
        )
        return result.to_dict() if result.success else None
    except Exception as exc:
        logger.warning(
            "event=agent_dispatch_failed agent=onboarding learner=%s error=%s",
            learner_id, exc,
        )
        return None


# ── Memory Timeline ───────────────────────────────────────────────────

def record_timeline_event(
    learner_id: str,
    event_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Record an event to the LearnerMemoryTimeline for the given learner.

    Fire-and-forget: failures are logged but never raised.
    """
    try:
        from app.memory.learner_timeline import LearnerMemoryTimeline

        timeline = LearnerMemoryTimeline(learner_id)
        timeline.add_event(event_type, content, metadata)  # type: ignore[arg-type]
        logger.info(
            "event=timeline_record learner=%s type=%s",
            learner_id, event_type,
        )
    except Exception as exc:
        logger.warning(
            "event=timeline_record_failed learner=%s error=%s",
            learner_id, exc,
        )


def record_timeline_reflection(
    learner_id: str,
    trigger: str,
    summary: str,
) -> None:
    """Record a reflection event to the LearnerMemoryTimeline."""
    try:
        from app.memory.learner_timeline import LearnerMemoryTimeline

        timeline = LearnerMemoryTimeline(learner_id)
        timeline.add_reflection(trigger, summary)
    except Exception as exc:
        logger.warning(
            "event=timeline_reflection_failed learner=%s error=%s",
            learner_id, exc,
        )


# ── Intervention Engine ───────────────────────────────────────────────

async def dispatch_interventions(
    learner_id: str,
    db_session: Any,
) -> list[dict] | None:
    """
    Run intervention engine for the given learner, deriving any needed
    interventions based on current state.

    Returns list of interventions or *None* on failure.
    """
    try:
        from app.services.learner_state_profile import build_learner_state_profile
        from app.services.intervention_engine import derive_interventions

        state = await build_learner_state_profile(learner_id, db_session)
        interventions = derive_interventions(state)
        if interventions:
            logger.info(
                "event=interventions_derived learner=%s count=%d",
                learner_id, len(interventions),
            )
        return interventions
    except Exception as exc:
        logger.warning(
            "event=intervention_dispatch_failed learner=%s error=%s",
            learner_id, exc,
        )
        return None
