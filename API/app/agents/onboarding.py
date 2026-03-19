"""
OnboardingAgent — processes diagnostic results and produces onboarding summaries.

Enriched from stub to compute mastery analysis, risk assessment, weak area
identification, and recommended starting pace from diagnostic data.
"""
from __future__ import annotations

from typing import Any

from app.agents.agent_interface import AgentContext, AgentInterface, AgentResult
from app.agents.base import BaseAgent


# ── Risk thresholds ──────────────────────────────────────────────────
HIGH_RISK_MASTERY = 0.4
"""Average mastery below this triggers high risk classification."""
MEDIUM_RISK_MASTERY = 0.65
"""Average mastery below this triggers medium risk classification."""
WEAK_CONCEPT_THRESHOLD = 0.5
"""Concepts below this mastery are classified as weak."""


class OnboardingAgent(BaseAgent, AgentInterface):
    """Processes diagnostic results and produces onboarding intelligence."""

    name = "onboarding_agent"
    role = "planner"
    capabilities = ("summarize_onboarding", "recommend_pace")
    reads = ["LearnerProfile", "EmbeddingChunk"]
    writes = ["LearnerProfile", "WeeklyPlan", "AgentDecision"]

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Legacy BaseAgent interface: produce onboarding summary from mastery map."""
        learner_id = input_data.get("learner_id", "unknown")
        mastery_map = input_data.get("mastery_map", {})
        weak = sorted(mastery_map.items(), key=lambda x: x[1])[:3]
        avg_mastery = (sum(mastery_map.values()) / len(mastery_map)) if mastery_map else 0.0
        risk_level = "high" if avg_mastery < HIGH_RISK_MASTERY else "medium" if avg_mastery < MEDIUM_RISK_MASTERY else "low"
        return {
            "learner_id": learner_id,
            "avg_mastery": round(avg_mastery, 4),
            "weak_concepts": [concept for concept, _ in weak],
            "risk_level": risk_level,
        }

    async def _execute(self, context: AgentContext) -> AgentResult:
        """
        AgentInterface entry point: analyze diagnostic results.

        Expected context.extra keys:
            mastery_map (dict): chapter → score mapping
            diagnostic_score (float): overall diagnostic score 0-1
            selected_timeline_weeks (int): student-selected timeline
        """
        mastery_map: dict[str, float] = context.extra.get("mastery_map", {})
        diagnostic_score = float(context.extra.get("diagnostic_score", 0.0))
        selected_weeks = int(context.extra.get("selected_timeline_weeks", 16))

        # Compute analytics
        if mastery_map:
            avg_mastery = sum(mastery_map.values()) / len(mastery_map)
            weak_concepts = sorted(
                [k for k, v in mastery_map.items() if v < WEAK_CONCEPT_THRESHOLD],
                key=lambda k: mastery_map[k],
            )
            strong_concepts = [k for k, v in mastery_map.items() if v >= 0.75]
        else:
            avg_mastery = 0.0
            weak_concepts = []
            strong_concepts = []

        # Risk classification
        if avg_mastery < HIGH_RISK_MASTERY:
            risk_level = "high"
        elif avg_mastery < MEDIUM_RISK_MASTERY:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Pace recommendation based on diagnostic
        pace_adjustment = 0
        if diagnostic_score >= 0.85:
            pace_adjustment = -1
        elif diagnostic_score < 0.55:
            pace_adjustment = 2
        elif diagnostic_score < 0.40:
            pace_adjustment = 4

        recommended_weeks = max(14, min(28, selected_weeks + pace_adjustment))

        # Starting difficulty recommendation
        if avg_mastery >= 0.7:
            starting_depth = "advanced"
        elif avg_mastery >= 0.4:
            starting_depth = "standard"
        else:
            starting_depth = "foundational"

        return AgentResult(
            success=True,
            agent_name=self.name,
            decision=f"risk_{risk_level}_pace_{recommended_weeks}w",
            reasoning=(
                f"Diagnostic score {diagnostic_score:.2f}, avg mastery {avg_mastery:.2f}. "
                f"{len(weak_concepts)} weak areas identified. "
                f"Risk: {risk_level}. Recommended {recommended_weeks} weeks."
            ),
            data={
                "avg_mastery": round(avg_mastery, 4),
                "diagnostic_score": round(diagnostic_score, 4),
                "risk_level": risk_level,
                "weak_concepts": weak_concepts[:5],
                "strong_concepts": strong_concepts[:5],
                "recommended_timeline_weeks": recommended_weeks,
                "starting_depth": starting_depth,
                "pace_adjustment": pace_adjustment,
            },
        )
