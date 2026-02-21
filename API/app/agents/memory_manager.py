from app.agents.base import BaseAgent
from app.memory.ingest import ingest_session_signal


class MemoryManagementAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        learner_id = str(input_data.get("learner_id"))
        concept = str(input_data.get("concept"))
        score = float(input_data.get("score", 0.0))
        adaptation_score = float(input_data.get("adaptation_score", 0.0))
        ingest_session_signal(
            learner_id=learner_id,
            concept=concept,
            score=score,
            adaptation_score=adaptation_score,
        )
        return {
            "learner_id": learner_id,
            "concept": concept,
            "memory_update": "applied",
            "adaptation_score": adaptation_score,
        }
