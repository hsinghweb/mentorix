"""
Alembic migration: Add GIN index for full-text search on embedding_chunks.

Creates a PostgreSQL GIN index on `to_tsvector('english', content)` for the
embedding_chunks table to accelerate the hybrid retriever's keyword search path.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "v018_gin_fts_index"
down_revision = None  # chain with latest existing migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create GIN index for full-text search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_embedding_chunks_content_fts
        ON embedding_chunks
        USING GIN (to_tsvector('english', content))
        """
    )
    # Create trigram index for ILIKE fallback
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS pg_trgm
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_embedding_chunks_content_trgm
        ON embedding_chunks
        USING GIN (content gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_embedding_chunks_content_fts")
