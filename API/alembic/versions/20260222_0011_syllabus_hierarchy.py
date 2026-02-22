"""add syllabus hierarchy (chapter > section > concept)

Revision ID: 20260222_0011
Revises: 20260222_0010
Create Date: 2026-02-22 22:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260222_0011"
down_revision = "20260222_0010"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("syllabus_hierarchy"):
        op.create_table(
            "syllabus_hierarchy",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=512), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["document_id"], ["curriculum_documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["syllabus_hierarchy.id"], ondelete="CASCADE"),
        )
        op.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_hierarchy_document_id ON syllabus_hierarchy (document_id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_hierarchy_parent_id ON syllabus_hierarchy (parent_id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_syllabus_hierarchy_type ON syllabus_hierarchy (type)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_syllabus_hierarchy_type")
    op.execute("DROP INDEX IF EXISTS idx_syllabus_hierarchy_parent_id")
    op.execute("DROP INDEX IF EXISTS idx_syllabus_hierarchy_document_id")
    op.drop_table("syllabus_hierarchy")
