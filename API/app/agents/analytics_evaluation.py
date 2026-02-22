from app.agents.base import BaseAgent


def _score_trend(scores: list[float]) -> str:
    if len(scores) <= 1:
        return "flat"
    return "up" if scores[-1] >= scores[0] else "down"


def _misconception_patterns(error_types: list[str]) -> list[dict]:
    misconceptions: dict[str, int] = {}
    for err in error_types:
        key = str(err or "none").strip().lower()
        if key in ("", "none"):
            continue
        misconceptions[key] = misconceptions.get(key, 0) + 1
    return [
        {"error_type": key, "count": value}
        for key, value in sorted(misconceptions.items(), key=lambda item: item[1], reverse=True)
    ]


def _risk_level(avg_score: float, trend: str, avg_response: float) -> str:
    if avg_score < 0.5 or (trend == "down" and avg_score < 0.65):
        return "high"
    if avg_score < 0.75 or avg_response > 20.0:
        return "medium"
    return "low"


def _recommendations(risk_level: str, patterns: list[dict]) -> list[str]:
    recs = {
        "high": "Assign reinforced practice with guided examples before next chapter progression.",
        "medium": "Schedule mixed practice and a quick revision checkpoint in the current week.",
        "low": "Continue progression and add one challenge set to maintain momentum.",
    }
    output = [recs.get(risk_level, recs["medium"])]
    if patterns:
        output.append(f"Prioritize remediation for '{patterns[0]['error_type']}' mistakes in next practice block.")
    return output


class AnalyticsEvaluationAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        recent_scores = [float(v) for v in input_data.get("recent_scores", [])]
        response_times = [float(v) for v in input_data.get("recent_response_times", [])]
        recent_error_types = [str(v or "none") for v in input_data.get("recent_error_types", [])]
        avg_score = (sum(recent_scores) / len(recent_scores)) if recent_scores else 0.0
        trend = _score_trend(recent_scores)
        avg_response = (sum(response_times) / len(response_times)) if response_times else 0.0
        if avg_score < 0.5:
            misconception_risk = "high"
        elif avg_score < 0.75:
            misconception_risk = "medium"
        else:
            misconception_risk = "low"
        trend_bonus = 0.2 if trend == "up" else 0.0
        readiness_prediction = max(0.0, min(1.0, (avg_score * 0.8) + trend_bonus))
        misconception_patterns = _misconception_patterns(recent_error_types)
        risk_level = _risk_level(avg_score, trend, avg_response)
        recommendations = _recommendations(risk_level, misconception_patterns)
        return {
            "objective_evaluation": {
                "attempted_questions": len(recent_scores),
                "latest_score": round(recent_scores[-1], 4) if recent_scores else 0.0,
                "avg_score": round(avg_score, 4),
            },
            "avg_score": round(avg_score, 4),
            "score_trend": trend,
            "avg_response_time": round(avg_response, 4),
            "misconception_risk": misconception_risk,
            "misconception_patterns": misconception_patterns,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "readiness_prediction": round(readiness_prediction, 4),
        }
