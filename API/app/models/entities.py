import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
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


class LearnerProfile(Base):
    __tablename__ = "learner_profile"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True
    )
    concept_mastery: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retention_decay: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    cognitive_depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


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
