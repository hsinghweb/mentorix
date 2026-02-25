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
    idempotency_key: str | None = Field(default=None, max_length=128)


class ChapterPlan(BaseModel):
    week: int
    chapter: str
    focus: str


class TaskItem(BaseModel):
    task_id: UUID
    chapter: str
    task_type: str
    title: str
    week_number: int
    sort_order: int
    status: str
    is_locked: bool
    proof_policy: dict


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
    current_week_tasks: list[TaskItem] = Field(default_factory=list)


class WeeklyChapterEvaluation(BaseModel):
    chapter: str
    score: float = Field(ge=0.0, le=1.0)


class WeeklyReplanRequest(BaseModel):
    learner_id: UUID
    evaluation: WeeklyChapterEvaluation
    threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    max_attempts: int = Field(default=3, ge=1, le=6)
    idempotency_key: str | None = Field(default=None, max_length=128)


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
    committed_week_schedule: ChapterPlan | None = None
    forecast_plan: list[ChapterPlan] = Field(default_factory=list)
    current_week_tasks: list[TaskItem] = Field(default_factory=list)
    current_week_daily_breakdown: list[dict] = Field(default_factory=list)
    planning_mode: dict = Field(default_factory=dict)
    completion_estimate_weeks: int | None = None
    completion_estimate_vs_goal_weeks: int | None = None


class TaskCompletionRequest(BaseModel):
    learner_id: UUID
    reading_minutes: int = Field(default=0, ge=0, le=600)
    test_attempt_id: str | None = None
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class TaskCompletionResponse(BaseModel):
    learner_id: UUID
    task_id: UUID
    accepted: bool
    reason: str
    status: str


class ChapterAdvanceRequest(BaseModel):
    learner_id: UUID
    chapter: str
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    allow_policy_override: bool = False
    override_reason: str | None = None


class ChapterAdvanceResponse(BaseModel):
    learner_id: UUID
    chapter: str
    advanced: bool
    used_policy_override: bool
    reason: str


class RevisionQueueItemResponse(BaseModel):
    chapter: str
    status: str
    priority: int
    reason: str


class RevisionPolicyStateResponse(BaseModel):
    learner_id: UUID
    active_pass: int
    retention_score: float
    pass1_completed: bool
    pass2_completed: bool
    weak_zones: list[str]
    next_actions: list[str]


class EngagementEventRequest(BaseModel):
    learner_id: UUID
    event_type: Literal["login", "logout", "study", "task_completion", "test_submission"]
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    details: dict = Field(default_factory=dict)


class EngagementEventResponse(BaseModel):
    learner_id: UUID
    event_type: str
    duration_minutes: int
    accepted: bool


class EngagementSummaryResponse(BaseModel):
    learner_id: UUID
    engagement_minutes_today: int
    engagement_minutes_week: int
    login_streak_days: int
    adherence_rate_week: float
    last_login_at: datetime | None = None
    last_logout_at: datetime | None = None


class LearnerStandResponse(BaseModel):
    learner_id: UUID
    chapter_status: list[dict]
    concept_strengths: list[str]
    concept_weaknesses: list[str]
    confidence_score: float
    retention_score: float
    adherence_rate_week: float


class EvaluationAnalyticsResponse(BaseModel):
    learner_id: UUID
    objective_evaluation: dict
    misconception_patterns: list[dict]
    risk_level: Literal["low", "medium", "high"]
    recommendations: list[str]
    chapter_attempt_summary: list[dict]


class DailyPlanResponse(BaseModel):
    learner_id: UUID
    week_number: int
    chapter: str | None = None
    is_committed_week: bool
    forecast_read_only: bool
    daily_breakdown: list[dict] = Field(default_factory=list)


class StudentLearningMetricsResponse(BaseModel):
    """Aggregated student-learning metrics for monitoring/dashboards."""
    learner_id: UUID
    mastery_progression: dict  # chapter -> score (or summary)
    avg_mastery_score: float
    confidence_score: float
    weak_area_count: int
    weak_areas: list[str]
    adherence_rate_week: float
    login_streak_days: int
    timeline_adherence_weeks: int | None  # delta (current_forecast - selected); negative = ahead
    forecast_drift_weeks: int | None  # same as timeline_adherence_weeks for "drift from goal"
    selected_timeline_weeks: int | None
    current_forecast_weeks: int | None
    chapter_retry_counts: dict[str, int] = Field(default_factory=dict)


class ForecastHistoryItem(BaseModel):
    week_number: int
    current_forecast_weeks: int
    timeline_delta_weeks: int
    pacing_status: str
    generated_at: datetime


class ForecastHistoryResponse(BaseModel):
    learner_id: UUID
    history: list[ForecastHistoryItem]
