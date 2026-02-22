"""add weekly forecasts table

Revision ID: 20260222_0005
Revises: 20260222_0004
Create Date: 2026-02-22 18:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0005"
down_revision = "20260222_0004"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("weekly_forecasts"):
        return

    op.create_table(
        "weekly_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("selected_timeline_weeks", sa.Integer(), nullable=False),
        sa.Column("recommended_timeline_weeks", sa.Integer(), nullable=False),
        sa.Column("current_forecast_weeks", sa.Integer(), nullable=False),
        sa.Column("timeline_delta_weeks", sa.Integer(), nullable=False),
        sa.Column("pacing_status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_forecasts_learner_id ON weekly_forecasts (learner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_forecasts_generated_at ON weekly_forecasts (generated_at)")


def downgrade() -> None:
    op.drop_index("idx_weekly_forecasts_generated_at", table_name="weekly_forecasts")
    op.drop_index("idx_weekly_forecasts_learner_id", table_name="weekly_forecasts")
    op.drop_table("weekly_forecasts")
