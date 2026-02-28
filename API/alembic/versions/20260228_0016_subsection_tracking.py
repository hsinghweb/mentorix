"""add section_id to embedding_chunks and create subsection_progression table

Revision ID: 20260228_0016
Revises: 20260226_0015
Create Date: 2026-02-28

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260228_0016"
down_revision = "20260226_0015"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_table(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add section_id column to embedding_chunks
    if _has_table(inspector, "embedding_chunks") and not _has_column(inspector, "embedding_chunks", "section_id"):
        op.add_column(
            "embedding_chunks",
            sa.Column("section_id", sa.String(16), nullable=True),
        )
        op.create_index("idx_embedding_chunks_section_id", "embedding_chunks", ["section_id"])

    # 2. Create subsection_progression table
    if not _has_table(inspector, "subsection_progression"):
        op.create_table(
            "subsection_progression",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chapter", sa.String(128), nullable=False),
            sa.Column("section_id", sa.String(16), nullable=False),
            sa.Column("section_title", sa.String(255), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="not_started"),
            sa.Column("best_score", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("last_score", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("reading_completed", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_subsection_prog_learner_chapter", "subsection_progression", ["learner_id", "chapter"])
        op.create_index("idx_subsection_prog_learner_section", "subsection_progression", ["learner_id", "section_id"])
        op.create_index("idx_subsection_prog_status", "subsection_progression", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "subsection_progression"):
        op.drop_table("subsection_progression")

    if _has_table(inspector, "embedding_chunks") and _has_column(inspector, "embedding_chunks", "section_id"):
        op.drop_index("idx_embedding_chunks_section_id", table_name="embedding_chunks")
        op.drop_column("embedding_chunks", "section_id")
