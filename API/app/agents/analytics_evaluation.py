from app.agents.base import BaseAgent


class AnalyticsEvaluationAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        recent_scores = [float(v) for v in input_data.get("recent_scores", [])]
        response_times = [float(v) for v in input_data.get("recent_response_times", [])]
        if recent_scores:
            avg_score = sum(recent_scores) / len(recent_scores)
            trend = "up" if len(recent_scores) > 1 and recent_scores[-1] >= recent_scores[0] else "down"
        else:
            avg_score = 0.0
            trend = "flat"
        avg_response = (sum(response_times) / len(response_times)) if response_times else 0.0
        misconception_risk = "high" if avg_score < 0.5 else "medium" if avg_score < 0.75 else "low"
        readiness_prediction = max(0.0, min(1.0, (avg_score * 0.8) + (0.2 if trend == "up" else 0.0)))
        return {
            "avg_score": round(avg_score, 4),
            "score_trend": trend,
            "avg_response_time": round(avg_response, 4),
            "misconception_risk": misconception_risk,
            "readiness_prediction": round(readiness_prediction, 4),
        }
