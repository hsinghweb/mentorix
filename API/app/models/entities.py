import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.settings import settings
from app.models.base import Base


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[str] = mapped_column(String(32), nullable=False, default="10")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentAuth(Base):
    """Credentials for login; one-to-one with Learner (student)."""
    __tablename__ = "student_auth"
    __table_args__ = (Index("idx_student_auth_username", "username", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnerProfile(Base):
    __tablename__ = "learner_profile"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True
    )
    concept_mastery: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retention_decay: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    cognitive_depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    math_9_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_diagnostic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    selected_timeline_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_timeline_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_forecast_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeline_delta_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearnerProfileSnapshot(Base):
    __tablename__ = "learner_profile_snapshots"
    __table_args__ = (
        Index("idx_profile_snapshots_learner_created", "learner_id", "created_at"),
        Index("idx_profile_snapshots_reason", "reason"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="profile_update")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    __table_args__ = (
        Index("idx_engagement_events_learner_created", "learner_id", "created_at"),
        Index("idx_engagement_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="study")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionLog(Base):
    __tablename__ = "session_logs"
    __table_args__ = (
        Index("idx_session_logs_learner_id", "learner_id"),
        Index("idx_session_logs_concept", "concept"),
        Index("idx_session_logs_timestamp", "timestamp"),
        Index("idx_session_logs_learner_timestamp", "learner_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    adaptation_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        Index("idx_assessment_results_learner_id", "learner_id"),
        Index("idx_assessment_results_concept", "concept"),
        Index("idx_assessment_results_timestamp", "timestamp"),
        Index("idx_assessment_results_learner_timestamp", "learner_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    response_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_type: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConceptChunk(Base):
    __tablename__ = "concept_chunks"
    __table_args__ = (
        Index("idx_concept_chunks_concept_difficulty", "concept", "difficulty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions), nullable=False)


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"
    __table_args__ = (
        Index("idx_generated_artifacts_concept", "concept"),
        Index("idx_generated_artifacts_type", "artifact_type"),
        Index("idx_generated_artifacts_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    concept: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, default="explanation")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CurriculumDocument(Base):
    __tablename__ = "curriculum_documents"
    __table_args__ = (
        Index("idx_curriculum_documents_doc_type", "doc_type"),
        Index("idx_curriculum_documents_source_path", "source_path"),
        Index("idx_curriculum_documents_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)  # syllabus | chapter
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"
    __table_args__ = (
        Index("idx_embedding_chunks_doc_id", "document_id"),
        Index("idx_embedding_chunks_doc_type_chapter", "doc_type", "chapter_number"),
        Index("idx_embedding_chunks_chunk_index", "chunk_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyllabusHierarchy(Base):
    """Chapter > section > concept hierarchy parsed from syllabus/chapter documents."""
    __tablename__ = "syllabus_hierarchy"
    __table_args__ = (
        Index("idx_syllabus_hierarchy_document_id", "document_id"),
        Index("idx_syllabus_hierarchy_parent_id", "parent_id"),
        Index("idx_syllabus_hierarchy_type", "type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("syllabus_hierarchy.id", ondelete="CASCADE"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # chapter | section | concept
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("idx_ingestion_runs_started_at", "started_at"),
        Index("idx_ingestion_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (
        Index("idx_weekly_plans_learner_id", "learner_id"),
        Index("idx_weekly_plans_generated_at", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    plan_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeeklyPlanVersion(Base):
    __tablename__ = "weekly_plan_versions"
    __table_args__ = (
        Index("idx_weekly_plan_versions_plan_id_version", "weekly_plan_id", "version_number"),
        Index("idx_weekly_plan_versions_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    weekly_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    plan_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(String(128), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChapterProgression(Base):
    __tablename__ = "chapter_progression"
    __table_args__ = (
        Index("idx_chapter_progression_learner_chapter", "learner_id", "chapter"),
        Index("idx_chapter_progression_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    chapter: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    revision_queued: Mapped[bool] = mapped_column(nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WeeklyForecast(Base):
    __tablename__ = "weekly_forecasts"
    __table_args__ = (
        Index("idx_weekly_forecasts_learner_id", "learner_id"),
        Index("idx_weekly_forecasts_generated_at", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected_timeline_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_timeline_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    current_forecast_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    timeline_delta_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pacing_status: Mapped[str] = mapped_column(String(24), nullable=False, default="on_track")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="initial_forecast")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_learner_week", "learner_id", "week_number"),
        Index("idx_tasks_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chapter: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="read")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    is_locked: Mapped[bool] = mapped_column(nullable=False, default=True)
    proof_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskAttempt(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (
        Index("idx_task_attempts_task_id", "task_id"),
        Index("idx_task_attempts_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    proof_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    accepted: Mapped[bool] = mapped_column(nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="proof_required")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RevisionQueueItem(Base):
    __tablename__ = "revision_queue"
    __table_args__ = (
        Index("idx_revision_queue_learner_status", "learner_id", "status"),
        Index("idx_revision_queue_priority", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    chapter: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="low_mastery")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PolicyViolation(Base):
    __tablename__ = "policy_violations"
    __table_args__ = (
        Index("idx_policy_violations_learner_created", "learner_id", "created_at"),
        Index("idx_policy_violations_policy", "policy_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    chapter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RevisionPolicyState(Base):
    __tablename__ = "revision_policy_state"
    __table_args__ = (
        Index("idx_revision_policy_state_learner_id", "learner_id"),
        Index("idx_revision_policy_state_active_pass", "active_pass"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    active_pass: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pass1_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pass2_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    weak_zones: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    next_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
