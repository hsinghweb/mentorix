import re
from typing import Awaitable, Callable

from app.core.llm_provider import get_llm_provider
from app.core.settings import settings


class Verifier:
    def __init__(self):
        self.provider = get_llm_provider(role="verifier")
        self.fallback_provider = get_llm_provider(role="optimizer")

    async def verify(self, query: str, draft: str, context: str = "") -> tuple[int, str]:
        prompt = (
            "You are a strict verifier.\n"
            "Score the draft from 0-100 and provide critique.\n"
            "Output exactly:\nSCORE: <number>\nCRITIQUE: <text>\n\n"
            f"QUERY: {query}\nCONTEXT: {context}\nDRAFT: {draft}"
        )
        try:
            response, _usage = await self.provider.generate(prompt)
            if not response:
                return 100, "verification_skipped"
            score_match = re.search(r"SCORE:\s*(\d+)", response, re.IGNORECASE)
            critique_match = re.search(r"CRITIQUE:\s*(.*)", response, re.IGNORECASE | re.DOTALL)
            score = int(score_match.group(1)) if score_match else 50
            critique = critique_match.group(1).strip() if critique_match else response.strip()
            return max(0, min(100, score)), critique
        except Exception as exc:
            # Emergency remediation path: verifier local brain down -> cloud-ish fallback
            try:
                response, _usage = await self.fallback_provider.generate(prompt)
                if not response:
                    return 50, f"verification_failed: {exc}"
                score_match = re.search(r"SCORE:\s*(\d+)", response, re.IGNORECASE)
                critique_match = re.search(r"CRITIQUE:\s*(.*)", response, re.IGNORECASE | re.DOTALL)
                score = int(score_match.group(1)) if score_match else 50
                critique = critique_match.group(1).strip() if critique_match else response.strip()
                return max(0, min(100, score)), critique
            except Exception as fallback_exc:
                return 50, f"verification_failed: {exc}; fallback_failed: {fallback_exc}"


class ReasoningEngine:
    def __init__(self):
        self.verifier = Verifier()
        self.generator = get_llm_provider(role="content_generator")

    async def run_loop(
        self,
        *,
        query: str,
        generate_func: Callable[[], Awaitable[str]],
        context: str = "",
        max_refinements: int | None = None,
    ) -> tuple[str, list[dict]]:
        max_rounds = settings.reasoning_max_refinements if max_refinements is None else max_refinements
        current = await generate_func()
        history: list[dict] = []

        for idx in range(max_rounds + 1):
            score, critique = await self.verifier.verify(query, current, context)
            history.append({"round": idx + 1, "draft": current, "score": score, "critique": critique})
            if score >= settings.reasoning_score_threshold:
                return current, history
            if idx == max_rounds:
                best = max(history, key=lambda x: x["score"])
                return best["draft"], history

            refine_prompt = (
                "Improve this draft based on critique.\n"
                f"QUERY: {query}\nDRAFT: {current}\nCRITIQUE: {critique}\n"
                "Return improved draft only."
            )
            refined, _usage = await self.generator.generate(refine_prompt)
            current = refined or current

        return current, history


reasoning_engine = ReasoningEngine()
