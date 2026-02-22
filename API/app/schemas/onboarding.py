from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


QuestionType = Literal["mcq", "fill_blank", "true_false"]


class OnboardingStartRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    grade_level: str = Field(default="10", max_length=32)
    exam_in_months: int = Field(default=10, ge=1, le=18)
    selected_timeline_weeks: int = Field(default=14, ge=14, le=28)


class DiagnosticQuestion(BaseModel):
    question_id: str
    question_type: QuestionType
    chapter_number: int | None = None
    prompt: str
    options: list[str] = Field(default_factory=list)


class OnboardingStartResponse(BaseModel):
    learner_id: UUID
    diagnostic_attempt_id: str
    generated_at: datetime
    questions: list[DiagnosticQuestion]


class DiagnosticAnswer(BaseModel):
    question_id: str
    answer: str


class OnboardingSubmitRequest(BaseModel):
    learner_id: UUID
    diagnostic_attempt_id: str
    answers: list[DiagnosticAnswer]
    time_spent_minutes: int = Field(default=15, ge=1, le=240)


class ChapterPlan(BaseModel):
    week: int
    chapter: str
    focus: str


class OnboardingSubmitResponse(BaseModel):
    learner_id: UUID
    score: float
    selected_timeline_weeks: int
    recommended_timeline_weeks: int
    current_forecast_weeks: int
    timeline_delta_weeks: int
    timeline_recommendation_note: str
    chapter_scores: dict[str, float]
    profile_snapshot: dict
    rough_plan: list[ChapterPlan]
    current_week_schedule: ChapterPlan


class WeeklyChapterEvaluation(BaseModel):
    chapter: str
    score: float = Field(ge=0.0, le=1.0)


class WeeklyReplanRequest(BaseModel):
    learner_id: UUID
    evaluation: WeeklyChapterEvaluation
    threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    max_attempts: int = Field(default=3, ge=1, le=6)


class WeeklyReplanResponse(BaseModel):
    learner_id: UUID
    chapter: str
    score: float
    threshold: float
    attempt_count: int
    selected_timeline_weeks: int | None = None
    recommended_timeline_weeks: int | None = None
    current_forecast_weeks: int | None = None
    timeline_delta_weeks: int | None = None
    pacing_status: Literal["ahead", "on_track", "behind"] | None = None
    decision: Literal["repeat_chapter", "proceed_next_chapter", "proceed_with_revision_queue"]
    reason: str
    revision_queue: list[str]


class WeeklyPlanResponse(BaseModel):
    learner_id: UUID
    current_week: int
    total_weeks: int
    selected_timeline_weeks: int | None = None
    recommended_timeline_weeks: int | None = None
    current_forecast_weeks: int | None = None
    timeline_delta_weeks: int | None = None
    rough_plan: list[ChapterPlan]
