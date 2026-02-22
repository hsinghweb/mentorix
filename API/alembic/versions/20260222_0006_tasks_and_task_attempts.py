"""add tasks and task_attempts tables

Revision ID: 20260222_0006
Revises: 20260222_0005
Create Date: 2026-02-22 19:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260222_0006"
down_revision = "20260222_0005"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("tasks"):
        op.create_table(
            "tasks",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("week_number", sa.Integer(), nullable=False),
            sa.Column("chapter", sa.String(length=128), nullable=False),
            sa.Column("task_type", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("is_locked", sa.Boolean(), nullable=False),
            sa.Column("proof_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_learner_week ON tasks (learner_id, week_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)")

    if not inspector.has_table("task_attempts"):
        op.create_table(
            "task_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("proof_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("accepted", sa.Boolean(), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_attempts_task_id ON task_attempts (task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_attempts_learner_created ON task_attempts (learner_id, created_at)")


def downgrade() -> None:
    op.drop_index("idx_task_attempts_learner_created", table_name="task_attempts")
    op.drop_index("idx_task_attempts_task_id", table_name="task_attempts")
    op.drop_table("task_attempts")

    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_tasks_learner_week", table_name="tasks")
    op.drop_table("tasks")
