"""baseline schema with indexes and pgvector

Revision ID: 20260219_0001
Revises:
Create Date: 2026-02-19 15:10:00
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260219_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "learners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("grade_level", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "learner_profile",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept_mastery", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retention_decay", sa.Float(), nullable=False),
        sa.Column("cognitive_depth", sa.Float(), nullable=False),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("learner_id"),
    )

    op.create_table(
        "session_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept", sa.String(length=128), nullable=False),
        sa.Column("difficulty_level", sa.Integer(), nullable=False),
        sa.Column("adaptation_score", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_session_logs_learner_id", "session_logs", ["learner_id"], unique=False)
    op.create_index("idx_session_logs_concept", "session_logs", ["concept"], unique=False)
    op.create_index("idx_session_logs_timestamp", "session_logs", ["timestamp"], unique=False)
    op.create_index(
        "idx_session_logs_learner_timestamp",
        "session_logs",
        ["learner_id", "timestamp"],
        unique=False,
    )

    op.create_table(
        "assessment_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("response_time", sa.Float(), nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_assessment_results_learner_id", "assessment_results", ["learner_id"], unique=False)
    op.create_index("idx_assessment_results_concept", "assessment_results", ["concept"], unique=False)
    op.create_index("idx_assessment_results_timestamp", "assessment_results", ["timestamp"], unique=False)
    op.create_index(
        "idx_assessment_results_learner_timestamp",
        "assessment_results",
        ["learner_id", "timestamp"],
        unique=False,
    )

    op.create_table(
        "concept_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_concept_chunks_concept"), "concept_chunks", ["concept"], unique=False)
    op.create_index(
        "idx_concept_chunks_concept_difficulty",
        "concept_chunks",
        ["concept", "difficulty"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_concept_chunks_concept_difficulty", table_name="concept_chunks")
    op.drop_index(op.f("ix_concept_chunks_concept"), table_name="concept_chunks")
    op.drop_table("concept_chunks")

    op.drop_index("idx_assessment_results_learner_timestamp", table_name="assessment_results")
    op.drop_index("idx_assessment_results_timestamp", table_name="assessment_results")
    op.drop_index("idx_assessment_results_concept", table_name="assessment_results")
    op.drop_index("idx_assessment_results_learner_id", table_name="assessment_results")
    op.drop_table("assessment_results")

    op.drop_index("idx_session_logs_learner_timestamp", table_name="session_logs")
    op.drop_index("idx_session_logs_timestamp", table_name="session_logs")
    op.drop_index("idx_session_logs_concept", table_name="session_logs")
    op.drop_index("idx_session_logs_learner_id", table_name="session_logs")
    op.drop_table("session_logs")

    op.drop_table("learner_profile")
    op.drop_table("learners")
