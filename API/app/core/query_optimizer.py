from app.core.llm_provider import get_llm_provider
from app.core.json_parser import parse_llm_json
from app.telemetry.aggregator import fleet_telemetry_aggregator


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
            data = parse_llm_json(text)
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict):
                return {
                    "original": query,
                    "optimized": data.get("optimized_query", query),
                    "reasoning": data.get("changes_made", "optimized"),
                }
            return {"original": query, "optimized": query, "reasoning": "invalid_optimizer_json"}
        except Exception:
            return {"original": query, "optimized": query, "reasoning": "optimizer_failed"}

    async def get_jit_rules(self) -> str:
        metrics = fleet_telemetry_aggregator.aggregate()
        rules: list[str] = []
        top_agents = metrics.get("top_agents", [])
        if metrics.get("step_success_rate", 100.0) < 90.0:
            rules.append("Prefer decomposition into smaller steps for complex tasks.")
        if metrics.get("total_retries", 0) > 5:
            rules.append("When retries spike, simplify prompts and reduce tool fan-out.")
        for agent_name, count in top_agents[:2]:
            if count > 10:
                rules.append(f"Monitor {agent_name} closely; high execution frequency detected.")
        return "\n".join(rules)


query_optimizer = QueryOptimizer()
