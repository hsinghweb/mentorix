import logging
import json

from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider
from app.core.query_optimizer import query_optimizer
from app.core.reasoning import reasoning_engine
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ContentGenerationAgent(BaseAgent):
    def __init__(self):
        self.provider = get_llm_provider(role="content_generator")

    @staticmethod
    def _template_response(concept: str, difficulty: int, context: str) -> dict:
        explanation = (
            f"Concept: {concept}\n"
            f"Difficulty: {difficulty}\n\n"
            f"Grounded curriculum notes:\n{context}\n\n"
            "Step-by-step: Identify the known values, apply the concept rule, and verify the final answer."
        )
        return {
            "explanation": explanation,
            "examples": [f"Example 1 for {concept}", f"Example 2 for {concept}"],
            "breakdown": ["Understand definition", "Apply rule", "Check result"],
            "source": "template",
        }

    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        difficulty = input_data["difficulty"]
        chunks = input_data.get("retrieved_chunks", [])
        context = "\n".join(chunks[:3]) if chunks else f"Core concept: {concept}"
        optimization = await query_optimizer.optimize_query(f"Teach {concept} at difficulty {difficulty}")

        prompt = (
            "You are a math tutor generating a personalized explanation.\n"
            "You must only use the curriculum context provided below.\n"
            "If required information is missing, explicitly say what is missing.\n"
            "Keep language clear for class 10 students.\n\n"
            f"Concept: {concept}\n"
            f"Difficulty Level: {difficulty}\n"
            f"Optimized Goal: {optimization['optimized']}\n"
            f"Curriculum Context:\n{context}\n\n"
            "Return:\n"
            "1) Explanation\n"
            "2) Two short examples\n"
            "3) 3-step breakdown\n"
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
                        "examples": [f"Example 1 for {concept}", f"Example 2 for {concept}"],
                        "breakdown": ["Understand definition", "Apply rule", "Check result"],
                        "source": settings.llm_provider.lower(),
                        "_reasoning_trace": reasoning_trace,
                        "_optimized_query": optimization,
                    }
            except Exception as exc:
                logger.warning("LLM generation failed (attempt %s). Falling back path continues: %s", attempt + 1, exc)

        fallback = self._template_response(concept, difficulty, context)
        fallback["_reasoning_trace"] = reasoning_trace
        fallback["_optimized_query"] = optimization
        return fallback
