from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    learner_id: str = Field(..., description="Learner UUID")


class StartSessionResponse(BaseModel):
    session_id: str
    concept: str
    difficulty: int
    explanation: str
    question: str
    state: str


class SubmitAnswerRequest(BaseModel):
    session_id: str
    answer: str
    response_time: float = 0.0


class SubmitAnswerResponse(BaseModel):
    session_id: str
    score: float
    error_type: str
    adaptation_applied: dict
    next_explanation: str


class DashboardResponse(BaseModel):
    learner_id: str
    mastery_map: dict
    engagement_score: float
    weak_areas: list[str]
    last_sessions: list[dict]
