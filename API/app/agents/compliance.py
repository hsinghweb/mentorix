from app.agents.base import BaseAgent


class ComplianceAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        consecutive_failures = int(input_data.get("consecutive_failures", 0))
        response_time = float(input_data.get("response_time", 0.0))
        engagement_score = float(input_data.get("engagement_score", 0.5))
        inactivity_flag = response_time > 35.0
        disengagement_flag = consecutive_failures >= 2 or engagement_score < 0.4 or inactivity_flag
        if disengagement_flag:
            recommendation = "Trigger intervention: simplify content and send reminder"
        else:
            recommendation = "No intervention required"
        return {
            "inactivity_flag": inactivity_flag,
            "disengagement_flag": disengagement_flag,
            "recommendation": recommendation,
        }
