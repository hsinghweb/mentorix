"""add revision_policy_state table

Revision ID: 20260222_0009
Revises: 20260222_0008
Create Date: 2026-02-22 20:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0009"
down_revision = "20260222_0008"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("revision_policy_state"):
        return

    op.create_table(
        "revision_policy_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_pass", sa.Integer(), nullable=False),
        sa.Column("pass1_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pass2_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_score", sa.Float(), nullable=False),
        sa.Column("weak_zones", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_revision_policy_state_learner_id ON revision_policy_state (learner_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_revision_policy_state_active_pass ON revision_policy_state (active_pass)"
    )


def downgrade() -> None:
    op.drop_index("idx_revision_policy_state_active_pass", table_name="revision_policy_state")
    op.drop_index("idx_revision_policy_state_learner_id", table_name="revision_policy_state")
    op.drop_table("revision_policy_state")
