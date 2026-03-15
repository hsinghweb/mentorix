"""
ReflectionAgent — post-assessment reflection and mastery recalculation.

Enriched from stub to provide LLM-backed session debrief, mastery trend
analysis, engagement scoring, and retention decay adjustment.
"""
from __future__ import annotations

from typing import Any

from app.agents.agent_interface import AgentContext, AgentInterface, AgentResult
from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider


# ── Mastery blending weights ─────────────────────────────────────────
OLD_MASTERY_WEIGHT = 0.7
"""Weight given to existing mastery when blending with new score."""
NEW_SCORE_WEIGHT = 0.3
"""Weight given to current assessment score when blending."""

ENGAGEMENT_BOOST = 0.05
"""Engagement score increase for strong performance."""
ENGAGEMENT_PENALTY = -0.03
"""Engagement score decrease for weak performance."""
PERFORMANCE_THRESHOLD = 0.6
"""Score threshold separating positive from negative adjustments."""

RETENTION_DECAY_IMPROVE = 0.97
"""Multiplicative retention decay improvement factor for good scores."""
RETENTION_DECAY_DEGRADE = 1.03
"""Multiplicative retention decay degradation factor for poor scores."""
RETENTION_DECAY_MIN = 0.02
"""Minimum allowed retention decay value."""
RETENTION_DECAY_MAX = 0.5
"""Maximum allowed retention decay value."""


class ReflectionAgent(BaseAgent, AgentInterface):
    """Performs post-assessment reflection, mastery update, and session debrief."""

    name = "reflection_agent"
    role = "evaluator"
    capabilities = ("reflect_progress", "session_debrief")
    reads = ["LearnerProfile", "AssessmentResult", "ChapterProgression"]
    writes = ["LearnerProfile", "AgentDecision"]

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Legacy BaseAgent interface: compute mastery adjustments."""
        concept = input_data["concept"]
        old_mastery = float(input_data["mastery_map"].get(concept, 0.3))
        current_score = float(input_data["current_score"])
        engagement = float(input_data.get("engagement_score", 0.5))
        retention_decay = float(input_data.get("retention_decay", 0.1))

        new_mastery = (old_mastery * OLD_MASTERY_WEIGHT) + (current_score * NEW_SCORE_WEIGHT)
        if current_score >= PERFORMANCE_THRESHOLD:
            new_engagement = min(1.0, max(0.0, engagement + ENGAGEMENT_BOOST))
            new_retention = max(RETENTION_DECAY_MIN, min(RETENTION_DECAY_MAX, retention_decay * RETENTION_DECAY_IMPROVE))
        else:
            new_engagement = min(1.0, max(0.0, engagement + ENGAGEMENT_PENALTY))
            new_retention = max(RETENTION_DECAY_MIN, min(RETENTION_DECAY_MAX, retention_decay * RETENTION_DECAY_DEGRADE))

        return {
            "concept": concept,
            "new_mastery": round(new_mastery, 4),
            "engagement_score": round(new_engagement, 4),
            "retention_decay": round(new_retention, 4),
        }

    async def _execute(self, context: AgentContext) -> AgentResult:
        """
        AgentInterface entry point: full post-assessment reflection.

        Expected context.extra keys:
            concept (str): the concept/chapter being assessed
            current_score (float): latest assessment score 0-1
            mastery_map (dict): concept → mastery score mapping
            engagement_score (float): current engagement 0-1
            retention_decay (float): current retention decay factor
            assessment_count (int): number of assessments taken
        """
        concept = context.extra.get("concept", context.chapter or "unknown")
        current_score = float(context.extra.get("current_score", 0.5))
        mastery_map: dict[str, float] = context.extra.get("mastery_map", {})
        old_mastery = float(mastery_map.get(concept, 0.3))
        engagement = float(context.extra.get("engagement_score", 0.5))
        retention_decay = float(context.extra.get("retention_decay", 0.1))
        assessment_count = int(context.extra.get("assessment_count", 1))

        # Compute new metrics
        new_mastery = (old_mastery * OLD_MASTERY_WEIGHT) + (current_score * NEW_SCORE_WEIGHT)
        improving = current_score >= old_mastery
        if current_score >= PERFORMANCE_THRESHOLD:
            new_engagement = min(1.0, max(0.0, engagement + ENGAGEMENT_BOOST))
            new_retention = max(RETENTION_DECAY_MIN, min(RETENTION_DECAY_MAX, retention_decay * RETENTION_DECAY_IMPROVE))
        else:
            new_engagement = min(1.0, max(0.0, engagement + ENGAGEMENT_PENALTY))
            new_retention = max(RETENTION_DECAY_MIN, min(RETENTION_DECAY_MAX, retention_decay * RETENTION_DECAY_DEGRADE))

        # Determine recommendation
        if new_mastery >= 0.8:
            recommendation = "proceed_next"
            reasoning = f"Strong mastery ({new_mastery:.2f}) on {concept}. Ready to advance."
        elif new_mastery >= 0.6:
            recommendation = "proceed_with_review"
            reasoning = f"Adequate mastery ({new_mastery:.2f}) on {concept}. Proceed with revision queue entry."
        else:
            recommendation = "repeat_chapter"
            reasoning = f"Low mastery ({new_mastery:.2f}) on {concept}. Recommend repeating."

        # Attempt LLM-generated debrief for richer feedback
        debrief = ""
        try:
            provider = get_llm_provider(role="evaluator")
            debrief_prompt = (
                f"You are a supportive math tutor. The student scored {current_score:.0%} "
                f"on {concept} (previous mastery: {old_mastery:.0%}). "
                f"{'They are improving!' if improving else 'They need more practice.'} "
                f"Give ONE encouraging sentence of feedback (max 30 words)."
            )
            text, _ = await provider.generate(debrief_prompt)
            if text:
                debrief = text.strip()[:200]
        except Exception:
            debrief = (
                "Great progress! Keep practicing to solidify your understanding."
                if improving else
                "Don't worry — every attempt builds understanding. Let's review key concepts."
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            decision=recommendation,
            reasoning=reasoning,
            data={
                "concept": concept,
                "old_mastery": round(old_mastery, 4),
                "new_mastery": round(new_mastery, 4),
                "mastery_delta": round(new_mastery - old_mastery, 4),
                "engagement_score": round(new_engagement, 4),
                "retention_decay": round(new_retention, 4),
                "improving": improving,
                "assessment_count": assessment_count,
                "debrief": debrief,
                "recommendation": recommendation,
            },
        )
