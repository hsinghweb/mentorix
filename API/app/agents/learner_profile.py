from app.agents.base import BaseAgent


class LearnerProfilingAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        mastery = input_data.get("mastery_map", {})
        weak = sorted(mastery.items(), key=lambda x: x[1])[:3]
        return {
            "learner_profile": input_data,
            "mastery_map": mastery,
            "weak_concepts": [c for c, _ in weak],
        }
