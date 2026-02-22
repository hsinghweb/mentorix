"""add learner profile timeline fields

Revision ID: 20260222_0004
Revises: 20260221_0003
Create Date: 2026-02-22 18:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260222_0004"
down_revision = "20260221_0003"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learner_profile"):
        return

    if not _has_column(inspector, "learner_profile", "selected_timeline_weeks"):
        op.add_column("learner_profile", sa.Column("selected_timeline_weeks", sa.Integer(), nullable=True))
    if not _has_column(inspector, "learner_profile", "recommended_timeline_weeks"):
        op.add_column("learner_profile", sa.Column("recommended_timeline_weeks", sa.Integer(), nullable=True))
    if not _has_column(inspector, "learner_profile", "current_forecast_weeks"):
        op.add_column("learner_profile", sa.Column("current_forecast_weeks", sa.Integer(), nullable=True))
    if not _has_column(inspector, "learner_profile", "timeline_delta_weeks"):
        op.add_column("learner_profile", sa.Column("timeline_delta_weeks", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learner_profile"):
        return

    if _has_column(inspector, "learner_profile", "timeline_delta_weeks"):
        op.drop_column("learner_profile", "timeline_delta_weeks")
    if _has_column(inspector, "learner_profile", "current_forecast_weeks"):
        op.drop_column("learner_profile", "current_forecast_weeks")
    if _has_column(inspector, "learner_profile", "recommended_timeline_weeks"):
        op.drop_column("learner_profile", "recommended_timeline_weeks")
    if _has_column(inspector, "learner_profile", "selected_timeline_weeks"):
        op.drop_column("learner_profile", "selected_timeline_weeks")
