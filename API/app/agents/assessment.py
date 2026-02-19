from app.agents.base import BaseAgent


class AssessmentAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        difficulty = input_data["difficulty"]
        question = f"Solve one practice question for '{concept}' at difficulty level {difficulty}."
        expected_answer = concept.split("_")[0] if "_" in concept else concept.split()[0]
        return {"generated_question": question, "expected_answer": expected_answer.lower()}

    async def evaluate(self, answer: str, expected_answer: str) -> dict:
        answer_l = (answer or "").lower().strip()
        ok = expected_answer in answer_l and len(answer_l) > 8
        score = 1.0 if ok else 0.35
        error_type = "none" if ok else "concept_mismatch"
        return {"score": score, "error_type": error_type}
