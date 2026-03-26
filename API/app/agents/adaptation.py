"""
AdaptationAgent — adjusts content difficulty and delivery strategy based on
multi-signal learner performance analysis.

Enriched from a simple heuristic (40 lines) to a full agent with:
- Multi-signal input (mastery, engagement, retention, velocity)
- LLM-backed strategy recommendation with structured output parsing
- Deterministic fallback when LLM is unavailable
- Logging and tracing integration via AgentInterface circuit breaker
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.agents.agent_interface import AgentContext, AgentInterface, AgentResult
from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider


class AdaptationAgent(BaseAgent, AgentInterface):
    """Adjusts content difficulty and delivery strategy using multi-signal analysis."""

    name = "adaptation_agent"
    role = "executor"
    capabilities = ("adapt_strategy", "adjust_difficulty")
    reads = ["LearnerProfile", "ChapterProgression", "EngagementEvent"]
    writes = ["AgentDecision"]

    # ── Scoring thresholds ───────────────────────────────────────────
    STRUGGLING_THRESHOLD = 0.4
    STRONG_THRESHOLD = 0.7
    DISENGAGE_THRESHOLD = 0.3
    HIGH_ENGAGE_THRESHOLD = 0.7

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Legacy BaseAgent interface: simple heuristic adaptation."""
        error_rate = float(input_data.get("rolling_error_rate", 0.0))
        response_time_deviation = float(input_data.get("response_time_deviation", 0.0))
        consecutive_failures = float(input_data.get("consecutive_failures", 0.0))
        difficulty = int(input_data.get("difficulty", 1))
        cooldown_remaining = int(input_data.get("cooldown_remaining", 0))

        adaptation_score = (0.4 * error_rate) + (0.3 * response_time_deviation) + (0.3 * consecutive_failures)
        new_difficulty = difficulty
        granularity = "normal"
        analogy_flag = False

        if cooldown_remaining <= 0:
            if adaptation_score > 0.6:
                new_difficulty = max(1, difficulty - 1)
                granularity = "high"
                analogy_flag = True
                cooldown_remaining = 2
            elif adaptation_score < 0.3:
                new_difficulty = min(3, difficulty + 1)
                granularity = "compact"
                analogy_flag = False
                cooldown_remaining = 2
        else:
            cooldown_remaining -= 1

        return {
            "adaptation_score": adaptation_score,
            "new_difficulty": new_difficulty,
            "explanation_granularity_level": granularity,
            "analogy_injection_flag": analogy_flag,
            "cooldown_remaining": cooldown_remaining,
        }

    async def _execute(self, context: AgentContext) -> AgentResult:
        """
        AgentInterface entry point: analyse multi-signal learner state and
        recommend content adaptation strategy.

        Expected context.extra keys:
            mastery_map (dict): concept → mastery score (0-1)
            engagement_score (float): overall engagement level (0-1)
            retention_decay (float): current retention decay factor
            chapters_completed (int): number of chapters completed
            total_chapters (int): total chapters in curriculum
            current_difficulty (int): current difficulty level (1-3)
            recent_scores (list[float]): recent test scores
            time_spent_minutes (float): average time per chapter
        """
        mastery_map = context.extra.get("mastery_map", {})
        engagement = float(context.extra.get("engagement_score", 0.5))
        retention_decay = float(context.extra.get("retention_decay", 0.1))
        current_difficulty = int(context.extra.get("current_difficulty", 2))
        recent_scores = context.extra.get("recent_scores", [])
        chapters_completed = int(context.extra.get("chapters_completed", 0))
        total_chapters = int(context.extra.get("total_chapters", 15))

        # ── Multi-signal analysis ────────────────────────────────────
        avg_mastery = (
            sum(mastery_map.values()) / len(mastery_map)
            if mastery_map else 0.5
        )
        avg_recent = (
            sum(recent_scores) / len(recent_scores)
            if recent_scores else 0.5
        )
        velocity = chapters_completed / max(1, total_chapters)
        weak_concepts = [
            c for c, m in mastery_map.items() if m < self.STRUGGLING_THRESHOLD
        ]

        # ── Deterministic baseline decision ──────────────────────────
        decision = self._deterministic_adaptation(
            avg_mastery, avg_recent, engagement, retention_decay,
            current_difficulty, weak_concepts, velocity,
        )

        # ── LLM enrichment (optional) ───────────────────────────────
        llm_recommendation = None
        try:
            llm_recommendation = await self._llm_recommendation(
                context, avg_mastery, avg_recent, engagement,
                retention_decay, weak_concepts, velocity,
            )
            if llm_recommendation:
                decision["llm_recommendation"] = llm_recommendation
                decision["reasoning"] = llm_recommendation.get("reasoning", decision["reasoning"])
        except Exception as exc:
            decision["llm_fallback"] = True
            decision["llm_error"] = str(exc)

        return AgentResult(
            success=True,
            agent_name=self.name,
            decision=decision.get("strategy", "maintain"),
            reasoning=decision.get("reasoning", ""),
            data=decision,
        )

    def _deterministic_adaptation(
        self,
        avg_mastery: float,
        avg_recent: float,
        engagement: float,
        retention_decay: float,
        current_difficulty: int,
        weak_concepts: list[str],
        velocity: float,
    ) -> dict[str, Any]:
        """Pure-heuristic adaptation when LLM is unavailable."""
        strategy = "maintain"
        new_difficulty = current_difficulty
        granularity = "normal"
        use_analogies = False
        reasoning_parts: list[str] = []

        # Struggling learner: simplify
        if avg_mastery < self.STRUGGLING_THRESHOLD or avg_recent < 0.4:
            strategy = "simplify"
            new_difficulty = max(1, current_difficulty - 1)
            granularity = "high"
            use_analogies = True
            reasoning_parts.append(
                f"Low mastery ({avg_mastery:.2f}) or recent scores ({avg_recent:.2f}) indicate struggling."
            )

        # Strong learner: challenge
        elif avg_mastery > self.STRONG_THRESHOLD and avg_recent > 0.7:
            strategy = "challenge"
            new_difficulty = min(3, current_difficulty + 1)
            granularity = "compact"
            use_analogies = False
            reasoning_parts.append(
                f"High mastery ({avg_mastery:.2f}) and scores ({avg_recent:.2f}) support advancement."
            )

        # Disengaged: re-engage
        if engagement < self.DISENGAGE_THRESHOLD:
            strategy = "re-engage"
            use_analogies = True
            granularity = "high"
            reasoning_parts.append(
                f"Low engagement ({engagement:.2f}) suggests need for re-engagement strategies."
            )

        # High retention decay: increase revision
        if retention_decay > 0.3:
            reasoning_parts.append(
                f"High retention decay ({retention_decay:.2f}) — recommend increased revision."
            )

        return {
            "strategy": strategy,
            "new_difficulty": new_difficulty,
            "explanation_granularity": granularity,
            "use_analogies": use_analogies,
            "weak_concepts": weak_concepts[:5],
            "weak_concept_count": len(weak_concepts),
            "signals": {
                "avg_mastery": round(avg_mastery, 4),
                "avg_recent_score": round(avg_recent, 4),
                "engagement": round(engagement, 4),
                "retention_decay": round(retention_decay, 4),
                "velocity": round(velocity, 4),
            },
            "reasoning": " ".join(reasoning_parts) if reasoning_parts else "Maintaining current strategy.",
        }

    async def _llm_recommendation(
        self,
        context: AgentContext,
        avg_mastery: float,
        avg_recent: float,
        engagement: float,
        retention_decay: float,
        weak_concepts: list[str],
        velocity: float,
    ) -> dict[str, Any] | None:
        """Request LLM-backed strategy recommendation."""
        provider = get_llm_provider()

        prompt = f"""You are an adaptive learning strategy advisor for an AI math tutor.

Given the following student performance signals:
- Average mastery: {avg_mastery:.2f}
- Average recent test score: {avg_recent:.2f}
- Engagement level: {engagement:.2f}
- Retention decay factor: {retention_decay:.2f}
- Completion velocity: {velocity:.2%}
- Weak concepts: {', '.join(weak_concepts[:5]) if weak_concepts else 'none identified'}

Recommend an adaptation strategy. Respond in JSON:
{{
  "strategy": "simplify|maintain|challenge|re-engage",
  "reasoning": "brief explanation",
  "recommended_focus": ["concept1", "concept2"],
  "tone_adjustment": "supportive|neutral|challenging",
  "revision_priority": "low|medium|high"
}}"""

        response = await provider.generate(
            prompt=prompt,
            role="adaptation",
        )
        if not response:
            return None

        # Parse structured output
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {"reasoning": text, "strategy": "maintain"}
