import logging
from urllib.parse import urlencode

import httpx

from app.agents.base import BaseAgent
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ContentGenerationAgent(BaseAgent):
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

    async def _gemini_generate(self, prompt: str) -> str | None:
        if settings.llm_provider.lower() != "gemini":
            return None
        if not settings.gemini_api_key:
            return None

        api_url = settings.gemini_api_url.strip()
        if not api_url:
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.llm_model}:generateContent"
            )

        if "key=" not in api_url:
            sep = "&" if "?" in api_url else "?"
            api_url = f"{api_url}{sep}{urlencode({'key': settings.gemini_api_key})}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            return text or None

    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        difficulty = input_data["difficulty"]
        chunks = input_data.get("retrieved_chunks", [])
        context = "\n".join(chunks[:3]) if chunks else f"Core concept: {concept}"

        prompt = (
            "You are a math tutor generating a personalized explanation.\n"
            "You must only use the curriculum context provided below.\n"
            "If required information is missing, explicitly say what is missing.\n"
            "Keep language clear for class 10 students.\n\n"
            f"Concept: {concept}\n"
            f"Difficulty Level: {difficulty}\n"
            f"Curriculum Context:\n{context}\n\n"
            "Return:\n"
            "1) Explanation\n"
            "2) Two short examples\n"
            "3) 3-step breakdown\n"
        )

        try:
            llm_text = await self._gemini_generate(prompt)
            if llm_text:
                return {
                    "explanation": llm_text,
                    "examples": [f"Example 1 for {concept}", f"Example 2 for {concept}"],
                    "breakdown": ["Understand definition", "Apply rule", "Check result"],
                    "source": "gemini",
                }
        except Exception as exc:
            logger.warning("Gemini generation failed. Falling back to template: %s", exc)

        return self._template_response(concept, difficulty, context)
