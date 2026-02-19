from app.agents.base import BaseAgent


class ContentGenerationAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        concept = input_data["concept"]
        difficulty = input_data["difficulty"]
        chunks = input_data.get("retrieved_chunks", [])
        context = "\n".join(chunks[:3]) if chunks else f"Core concept: {concept}"

        explanation = (
            f"Concept: {concept}\n"
            f"Difficulty: {difficulty}\n\n"
            f"Grounded curriculum notes:\n{context}\n\n"
            "Step-by-step: Identify the known values, apply the concept rule, and verify the final answer."
        )

        examples = [f"Example 1 for {concept}", f"Example 2 for {concept}"]
        breakdown = ["Understand definition", "Apply rule", "Check result"]
        return {"explanation": explanation, "examples": examples, "breakdown": breakdown}
