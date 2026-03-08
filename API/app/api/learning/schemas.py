"""
Learning API — Pydantic request/response schemas.

Extracted from the monolithic learning.py for maintainability.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID


class ContentRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)
    regenerate: bool = False
    task_id: UUID | None = None


class ContentResponse(BaseModel):
    chapter_number: int
    chapter_title: str
    content: str
    source: str  # "llm" | "rag_only" | "fallback"
    tone: str
    examples_count: int
    required_read_seconds: int = 60


class TestQuestion(BaseModel):
    question_id: str
    prompt: str
    options: list[str]
    chapter_number: int


class GenerateTestResponse(BaseModel):
    learner_id: str
    week_number: int
    chapter: str
    test_id: str | None = None
    questions: list[TestQuestion] = Field(default_factory=list)
    time_limit_minutes: int = 20
    source: str = "llm"
    blocked: bool = False
    reason_code: str | None = None
    pending_tasks: list[str] = Field(default_factory=list)


class TestAnswer(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)


class SubmitTestRequest(BaseModel):
    learner_id: UUID
    test_id: str
    answers: list[TestAnswer]
    task_id: UUID | None = None


class SubmitTestResponse(BaseModel):
    learner_id: str
    chapter: str
    score: float
    correct: int
    total: int
    passed: bool
    attempt_number: int
    max_attempts: int
    decision: str  # "chapter_completed" | "retry" | "move_on_revision"
    message: str
    question_results: list[dict] = Field(default_factory=list)


class CompleteReadingRequest(BaseModel):
    learner_id: UUID
    task_id: UUID
    time_spent_seconds: int = Field(ge=0)


class SubsectionContentRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)
    section_id: str  # e.g. "1.2", "3.3.1"
    regenerate: bool = False  # True = force LLM call, ignore cache
    task_id: UUID | None = None


class CompleteReadingResponse(BaseModel):
    task_id: str
    accepted: bool
    reason: str


class WeekCompleteResponse(BaseModel):
    learner_id: str
    completed_week: int
    new_week: int
    plan_updated: bool
    chapters_completed: list[str]
    revision_chapters: list[str]
    message: str


class DashboardResponse(BaseModel):
    learner_id: str
    student_name: str
    diagnostic_score: float | None
    math_9_percent: int | None
    selected_weeks: int | None
    suggested_weeks: int | None
    onboarding_date: str | None = None
    timeline_timezone: str = "UTC"
    current_week: int
    current_week_label: str | None = None
    current_week_start_date: str | None = None
    current_week_end_date: str | None = None
    total_weeks: int
    completion_estimate_date: str | None = None
    completion_estimate_date_active_pace: str | None = None
    completion_estimate_weeks_active_pace: int | None = None
    overall_completion_percent: float
    overall_mastery_percent: float
    rough_plan: list[dict]
    timeline_visualization: list[dict] = Field(default_factory=list)
    chapter_status: list[dict]
    chapter_confidence: list[dict]
    current_week_tasks: list[dict]
    revision_queue: list[dict]


class ExplainQuestionRequest(BaseModel):
    learner_id: UUID
    test_id: str
    question_id: str
    selected_index: int | None = None
    regenerate: bool = False


class ExplainQuestionResponse(BaseModel):
    learner_id: str
    test_id: str
    question_id: str
    chapter_number: int
    chapter: str
    section_id: str | None = None
    explanation: str
    source: str  # "cached" | "llm" | "fallback"


class SourceSectionResponse(BaseModel):
    chapter_number: int
    chapter_title: str
    section_id: str
    section_title: str
    source_type: str = "ncert"
    source_content: str
    chunk_count: int = 0


class SourceChapterResponse(BaseModel):
    chapter_number: int
    chapter_title: str
    source_type: str = "ncert"
    source_content: str
    chunk_count: int = 0
