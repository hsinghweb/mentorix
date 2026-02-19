from app.agents.base import BaseAgent


class ReflectionAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        old_mastery = float(input_data["mastery_map"].get(concept, 0.3))
        current_score = float(input_data["current_score"])
        engagement = float(input_data.get("engagement_score", 0.5))
        retention_decay = float(input_data.get("retention_decay", 0.1))

        new_mastery = (old_mastery * 0.7) + (current_score * 0.3)
        new_engagement = min(1.0, max(0.0, engagement + (0.05 if current_score >= 0.6 else -0.03)))
        new_retention = max(0.02, min(0.5, retention_decay * (0.97 if current_score >= 0.6 else 1.03)))

        return {
            "concept": concept,
            "new_mastery": round(new_mastery, 4),
            "engagement_score": round(new_engagement, 4),
            "retention_decay": round(new_retention, 4),
        }
