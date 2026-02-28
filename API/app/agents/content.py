import logging
import json

from app.agents.base import BaseAgent
from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.core.llm_provider import get_llm_provider
from app.core.query_optimizer import query_optimizer
from app.core.reasoning import reasoning_engine
from app.core.settings import settings

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)


class ContentGenerationAgent(BaseAgent):
    def __init__(self):
        self.provider = get_llm_provider(role="content_generator")

    @staticmethod
    def _derive_policy(concept: str, input_data: dict) -> dict:
        profile = input_data.get("profile_snapshot", {}) if isinstance(input_data, dict) else {}
        full_profile = input_data.get("student_profile", {}) if isinstance(input_data, dict) else {}
        mastery_map = profile.get("chapter_mastery") or profile.get("concept_mastery") or {}
        if not mastery_map and isinstance(full_profile, dict):
            mastery_map = full_profile.get("chapter_mastery") or full_profile.get("concept_mastery") or {}
        concept_score = 0.5
        if isinstance(mastery_map, dict):
            for key, value in mastery_map.items():
                if str(key).lower().replace(" ", "_") == str(concept).lower().replace(" ", "_"):
                    concept_score = float(value)
                    break

        if isinstance(full_profile, dict):
            engagement = float(full_profile.get("engagement_score", 0.5) or 0.5)
            cognitive_depth = float(full_profile.get("cognitive_depth", 0.5) or 0.5)
            concept_score = max(0.0, min(1.0, (0.5 * concept_score) + (0.3 * cognitive_depth) + (0.2 * engagement)))

        if concept_score < 0.45:
            return {
                "band": "weak",
                "pace": "slow",
                "tone": "simple_supportive",
                "depth": "foundational",
                "example_count": 3,
            }
        if concept_score < 0.70:
            return {
                "band": "developing",
                "pace": "balanced",
                "tone": "clear_structured",
                "depth": "standard",
                "example_count": 2,
            }
        return {
            "band": "strong",
            "pace": "fast",
            "tone": "concise_challenging",
            "depth": "advanced",
            "example_count": 1,
        }

    @staticmethod
    def _extract_grounded_context(chunks: list[str]) -> tuple[str, list[dict], bool]:
        clean_chunks = [str(c).strip() for c in (chunks or []) if str(c).strip()]
        curriculum_chunks = [c for c in clean_chunks if not c.lower().startswith("learner memory context:")]
        if not curriculum_chunks:
            return "", [], False
        citations = [
            {"id": f"C{i+1}", "snippet": chunk[:180]}
            for i, chunk in enumerate(curriculum_chunks[:3])
        ]
        context = "\n".join([f"[{cit['id']}] {chunk}" for cit, chunk in zip(citations, curriculum_chunks[:3])])
        return context, citations, True

    @staticmethod
    def _template_response(concept: str, difficulty: int, context: str, policy: dict, citations: list[dict]) -> dict:
        examples = [f"Example {i + 1} for {concept}" for i in range(int(policy.get("example_count", 2)))]
        explanation = (
            f"Concept: {concept}\n"
            f"Difficulty: {difficulty}\n\n"
            f"Adaptive policy: tone={policy.get('tone')}, pace={policy.get('pace')}, depth={policy.get('depth')}\n\n"
            f"Grounded curriculum notes:\n{context}\n\n"
            "Step-by-step: Identify the known values, apply the concept rule, and verify the final answer."
        )
        return {
            "explanation": explanation,
            "examples": examples,
            "breakdown": ["Understand definition", "Apply rule", "Check result"],
            "source": "template",
            "adaptation_policy": policy,
            "citations": citations,
            "grounding_status": "grounded",
        }

    @staticmethod
    def _grounding_guardrail(concept: str, policy: dict) -> dict:
        return {
            "explanation": (
                f"I could not find enough grounded curriculum context for '{concept}' right now. "
                "Please run grounding ingestion or retry with a specific chapter concept."
            ),
            "examples": [],
            "breakdown": ["Await grounded context", "Retry with chapter-aligned prompt", "Continue once sources are available"],
            "source": "grounding_guardrail",
            "adaptation_policy": policy,
            "citations": [],
            "grounding_status": "insufficient_context",
        }

    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        difficulty = input_data["difficulty"]
        chunks = input_data.get("retrieved_chunks", [])
        policy = self._derive_policy(concept, input_data)
        context, citations, is_grounded = self._extract_grounded_context(chunks)
        if not is_grounded:
            return self._grounding_guardrail(concept, policy)
        optimization = await query_optimizer.optimize_query(f"Teach {concept} at difficulty {difficulty}")

        prompt = (
            "You are a math tutor generating a personalized explanation.\n"
            "You must only use the curriculum context provided below.\n"
            "If required information is missing, explicitly say what is missing.\n"
            "Never use outside-syllabus content.\n"
            "Keep language clear for class 10 students.\n\n"
            f"Concept: {concept}\n"
            f"Difficulty Level: {difficulty}\n"
            f"Optimized Goal: {optimization['optimized']}\n"
            f"Adaptive Tone: {policy['tone']}\n"
            f"Adaptive Pace: {policy['pace']}\n"
            f"Adaptive Depth: {policy['depth']}\n"
            f"Examples Required: {policy['example_count']}\n"
            f"Curriculum Context:\n{context}\n\n"
            "Return:\n"
            "1) Explanation\n"
            "2) The requested number of short examples\n"
            "3) 3-step breakdown\n"
            "4) Include inline citation tags like [C1], [C2] where used.\n"
        )

        reasoning_trace: list[dict] = []

        async def _generate_draft() -> str:
            llm_text, usage = await self.provider.generate(prompt)
            logger.info(
                json.dumps(
                    {
                        "type": "llm_usage",
                        "agent": "content",
                        "usage": usage,
                        "query_optimization": optimization,
                    }
                )
            )
            return llm_text or ""

        # Guardrail: retries + reasoning loop before deterministic fallback.
        for attempt in range(2):
            try:
                llm_text, reasoning_trace = await reasoning_engine.run_loop(
                    query=optimization["optimized"],
                    generate_func=_generate_draft,
                    context=context,
                )
                if llm_text:
                    return {
                        "explanation": llm_text,
                        "examples": [f"Example {i + 1} for {concept}" for i in range(policy["example_count"])],
                        "breakdown": ["Understand definition", "Apply rule", "Check result"],
                        "source": settings.llm_provider.lower(),
                        "adaptation_policy": policy,
                        "citations": citations,
                        "grounding_status": "grounded",
                        "_reasoning_trace": reasoning_trace,
                        "_optimized_query": optimization,
                    }
            except Exception as exc:
                logger.warning("LLM generation failed (attempt %s). Falling back path continues: %s", attempt + 1, exc)

        fallback = self._template_response(concept, difficulty, context, policy, citations)
        fallback["_reasoning_trace"] = reasoning_trace
        fallback["_optimized_query"] = optimization
        return fallback
