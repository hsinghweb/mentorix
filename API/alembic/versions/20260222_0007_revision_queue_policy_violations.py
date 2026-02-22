"""add revision_queue and policy_violations tables

Revision ID: 20260222_0007
Revises: 20260222_0006
Create Date: 2026-02-22 19:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0007"
down_revision = "20260222_0006"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("revision_queue"):
        op.create_table(
            "revision_queue",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_revision_queue_learner_status ON revision_queue (learner_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_revision_queue_priority ON revision_queue (priority)")

    if not inspector.has_table("policy_violations"):
        op.create_table(
            "policy_violations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("policy_code", sa.String(length=64), nullable=False),
            sa.Column("chapter", sa.String(length=128), nullable=True),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_policy_violations_learner_created ON policy_violations (learner_id, created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_policy_violations_policy ON policy_violations (policy_code)")


def downgrade() -> None:
    op.drop_index("idx_policy_violations_policy", table_name="policy_violations")
    op.drop_index("idx_policy_violations_learner_created", table_name="policy_violations")
    op.drop_table("policy_violations")

    op.drop_index("idx_revision_queue_priority", table_name="revision_queue")
    op.drop_index("idx_revision_queue_learner_status", table_name="revision_queue")
    op.drop_table("revision_queue")
