from app.agents.base import BaseAgent


class CurriculumPlannerAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        mastery_map = input_data["mastery_map"]
        recent_concepts = input_data.get("recent_concepts", [])
        sorted_items = sorted(mastery_map.items(), key=lambda x: x[1])
        next_concept = sorted_items[0][0]

        for concept, _score in sorted_items:
            if concept not in recent_concepts[-3:]:
                next_concept = concept
                break

        target_difficulty = 1 if mastery_map.get(next_concept, 0.0) < 0.4 else 2
        return {"next_concept": next_concept, "target_difficulty": target_difficulty}
