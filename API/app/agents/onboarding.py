from app.agents.base import BaseAgent


class OnboardingAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        learner_id = input_data.get("learner_id", "unknown")
        mastery_map = input_data.get("mastery_map", {})
        weak = sorted(mastery_map.items(), key=lambda x: x[1])[:3]
        avg_mastery = (sum(mastery_map.values()) / len(mastery_map)) if mastery_map else 0.0
        risk_level = "high" if avg_mastery < 0.4 else "medium" if avg_mastery < 0.65 else "low"
        return {
            "learner_id": learner_id,
            "avg_mastery": round(avg_mastery, 4),
            "weak_concepts": [concept for concept, _ in weak],
            "risk_level": risk_level,
        }
