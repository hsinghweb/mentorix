"""add question_bank, agent_decisions and scheduled_day if missing

Revision ID: 20260228_0017
Revises: 20260228_0016
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260228_0017"
down_revision = "20260228_0016"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "tasks") and not _has_column(inspector, "tasks", "scheduled_day"):
        op.add_column("tasks", sa.Column("scheduled_day", sa.Date(), nullable=True))

    if not _has_table(inspector, "question_bank"):
        op.create_table(
            "question_bank",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("section_id", sa.String(length=16), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("options", JSONB(), nullable=False),
            sa.Column("correct_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="llm"),
            sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_question_bank_chapter_section", "question_bank", ["chapter_number", "section_id"])
        op.create_index("idx_question_bank_difficulty", "question_bank", ["difficulty"])

    if not _has_table(inspector, "agent_decisions"):
        op.create_table(
            "agent_decisions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_name", sa.String(length=64), nullable=False),
            sa.Column("decision_type", sa.String(length=64), nullable=False),
            sa.Column("chapter", sa.String(length=128), nullable=True),
            sa.Column("section_id", sa.String(length=16), nullable=True),
            sa.Column("input_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("output_payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_agent_decisions_learner", "agent_decisions", ["learner_id"])
        op.create_index("idx_agent_decisions_type", "agent_decisions", ["decision_type"])
        op.create_index("idx_agent_decisions_agent", "agent_decisions", ["agent_name"])
        op.create_index("idx_agent_decisions_created", "agent_decisions", ["created_at"])

    if _has_table(inspector, "question_bank"):
        if not _has_index(inspector, "question_bank", "idx_question_bank_chapter_section"):
            op.create_index("idx_question_bank_chapter_section", "question_bank", ["chapter_number", "section_id"])
        if not _has_index(inspector, "question_bank", "idx_question_bank_difficulty"):
            op.create_index("idx_question_bank_difficulty", "question_bank", ["difficulty"])
    if _has_table(inspector, "agent_decisions"):
        if not _has_index(inspector, "agent_decisions", "idx_agent_decisions_learner"):
            op.create_index("idx_agent_decisions_learner", "agent_decisions", ["learner_id"])
        if not _has_index(inspector, "agent_decisions", "idx_agent_decisions_type"):
            op.create_index("idx_agent_decisions_type", "agent_decisions", ["decision_type"])
        if not _has_index(inspector, "agent_decisions", "idx_agent_decisions_agent"):
            op.create_index("idx_agent_decisions_agent", "agent_decisions", ["agent_name"])
        if not _has_index(inspector, "agent_decisions", "idx_agent_decisions_created"):
            op.create_index("idx_agent_decisions_created", "agent_decisions", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "agent_decisions"):
        op.drop_table("agent_decisions")
    if _has_table(inspector, "question_bank"):
        op.drop_table("question_bank")
    if _has_table(inspector, "tasks") and _has_column(inspector, "tasks", "scheduled_day"):
        op.drop_column("tasks", "scheduled_day")
