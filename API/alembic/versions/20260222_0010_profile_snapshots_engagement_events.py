"""add learner profile snapshots and engagement events

Revision ID: 20260222_0010
Revises: 20260222_0009
Create Date: 2026-02-22 21:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0010"
down_revision = "20260222_0009"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("learner_profile_snapshots"):
        op.create_table(
            "learner_profile_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_profile_snapshots_learner_created "
        "ON learner_profile_snapshots (learner_id, created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_profile_snapshots_reason ON learner_profile_snapshots (reason)")

    if not inspector.has_table("engagement_events"):
        op.create_table(
            "engagement_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagement_events_learner_created "
        "ON engagement_events (learner_id, created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_engagement_events_event_type ON engagement_events (event_type)")


def downgrade() -> None:
    op.drop_index("idx_engagement_events_event_type", table_name="engagement_events")
    op.drop_index("idx_engagement_events_learner_created", table_name="engagement_events")
    op.drop_table("engagement_events")

    op.drop_index("idx_profile_snapshots_reason", table_name="learner_profile_snapshots")
    op.drop_index("idx_profile_snapshots_learner_created", table_name="learner_profile_snapshots")
    op.drop_table("learner_profile_snapshots")
