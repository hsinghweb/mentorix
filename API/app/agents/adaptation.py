from app.agents.base import BaseAgent


class AdaptationAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        error_rate = float(input_data.get("rolling_error_rate", 0.0))
        response_time_deviation = float(input_data.get("response_time_deviation", 0.0))
        consecutive_failures = float(input_data.get("consecutive_failures", 0.0))
        difficulty = int(input_data.get("difficulty", 1))
        cooldown_remaining = int(input_data.get("cooldown_remaining", 0))

        adaptation_score = (0.4 * error_rate) + (0.3 * response_time_deviation) + (0.3 * consecutive_failures)
        new_difficulty = difficulty
        granularity = "normal"
        analogy_flag = False

        if cooldown_remaining <= 0:
            if adaptation_score > 0.6:
                new_difficulty = max(1, difficulty - 1)
                granularity = "high"
                analogy_flag = True
                cooldown_remaining = 2
            elif adaptation_score < 0.3:
                new_difficulty = min(3, difficulty + 1)
                granularity = "compact"
                analogy_flag = False
                cooldown_remaining = 2
        else:
            cooldown_remaining -= 1

        return {
            "adaptation_score": adaptation_score,
            "new_difficulty": new_difficulty,
            "explanation_granularity_level": granularity,
            "analogy_injection_flag": analogy_flag,
            "cooldown_remaining": cooldown_remaining,
        }
