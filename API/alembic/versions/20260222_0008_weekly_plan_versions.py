"""add weekly_plan_versions table

Revision ID: 20260222_0008
Revises: 20260222_0007
Create Date: 2026-02-22 20:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0008"
down_revision = "20260222_0007"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("weekly_plan_versions"):
        return

    op.create_table(
        "weekly_plan_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekly_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("current_week", sa.Integer(), nullable=False),
        sa.Column("plan_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
        sa.ForeignKeyConstraint(["weekly_plan_id"], ["weekly_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_weekly_plan_versions_plan_id_version "
        "ON weekly_plan_versions (weekly_plan_id, version_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_weekly_plan_versions_learner_created "
        "ON weekly_plan_versions (learner_id, created_at)"
    )


def downgrade() -> None:
    op.drop_index("idx_weekly_plan_versions_learner_created", table_name="weekly_plan_versions")
    op.drop_index("idx_weekly_plan_versions_plan_id_version", table_name="weekly_plan_versions")
    op.drop_table("weekly_plan_versions")
