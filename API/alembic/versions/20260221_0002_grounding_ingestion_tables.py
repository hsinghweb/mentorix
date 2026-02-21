"""add grounding ingestion tables

Revision ID: 20260221_0002
Revises: 20260219_0001
Create Date: 2026-02-21 16:30:00
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260221_0002"
down_revision = "20260219_0001"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("curriculum_documents"):
        op.create_table(
            "curriculum_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("doc_type", sa.String(length=32), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("source_path", sa.String(length=512), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_hash", sa.String(length=128), nullable=False),
            sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_path"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_curriculum_documents_doc_type ON curriculum_documents (doc_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_curriculum_documents_source_path ON curriculum_documents (source_path)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_curriculum_documents_content_hash ON curriculum_documents (content_hash)"
    )

    if not inspector.has_table("embedding_chunks"):
        op.create_table(
            "embedding_chunks",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("doc_type", sa.String(length=32), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=128), nullable=False),
            sa.Column("embedding", Vector(768), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["document_id"], ["curriculum_documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_embedding_chunks_doc_id ON embedding_chunks (document_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_embedding_chunks_doc_type_chapter ON embedding_chunks (doc_type, chapter_number)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_embedding_chunks_chunk_index ON embedding_chunks (chunk_index)")

    if not inspector.has_table("ingestion_runs"):
        op.create_table(
            "ingestion_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("total_documents", sa.Integer(), nullable=False),
            sa.Column("total_chunks", sa.Integer(), nullable=False),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at ON ingestion_runs (started_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status ON ingestion_runs (status)")


def downgrade() -> None:
    op.drop_index("idx_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("idx_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index("idx_embedding_chunks_chunk_index", table_name="embedding_chunks")
    op.drop_index("idx_embedding_chunks_doc_type_chapter", table_name="embedding_chunks")
    op.drop_index("idx_embedding_chunks_doc_id", table_name="embedding_chunks")
    op.drop_table("embedding_chunks")

    op.drop_index("idx_curriculum_documents_content_hash", table_name="curriculum_documents")
    op.drop_index("idx_curriculum_documents_source_path", table_name="curriculum_documents")
    op.drop_index("idx_curriculum_documents_doc_type", table_name="curriculum_documents")
    op.drop_table("curriculum_documents")
