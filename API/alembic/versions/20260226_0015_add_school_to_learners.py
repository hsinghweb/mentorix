"""add school to learners

Revision ID: 20260226_0015
Revises: 20260225_0014
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa


revision = "20260226_0015"
down_revision = "20260225_0014"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learners"):
        return
    if not _has_column(inspector, "learners", "school"):
        op.add_column(
            "learners",
            sa.Column("school", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learners"):
        return
    if _has_column(inspector, "learners", "school"):
        op.drop_column("learners", "school")
