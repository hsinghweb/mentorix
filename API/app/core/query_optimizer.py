from app.core.llm_provider import get_llm_provider


class QueryOptimizer:
    def __init__(self):
        self.provider = get_llm_provider(role="optimizer")

    async def optimize_query(self, query: str) -> dict[str, str]:
        prompt = (
            "Rewrite the user request for an autonomous multi-agent system. "
            "Return strict JSON with keys optimized_query and changes_made.\n\n"
            f"User query: {query}"
        )
        try:
            text, _usage = await self.provider.generate(prompt)
            if not text:
                return {"original": query, "optimized": query, "reasoning": "No optimization output"}
            # Minimal robust parser without adding more dependencies.
            optimized = text
            if "optimized_query" in text:
                optimized = text.split("optimized_query", 1)[-1].split("\n", 1)[0].replace(":", "").strip(" \"{}")
            return {"original": query, "optimized": optimized or query, "reasoning": "optimized"}
        except Exception:
            return {"original": query, "optimized": query, "reasoning": "optimizer_failed"}


query_optimizer = QueryOptimizer()
