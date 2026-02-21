"""add weekly plan and chapter progression tables

Revision ID: 20260221_0003
Revises: 20260221_0002
Create Date: 2026-02-21 20:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260221_0003"
down_revision = "20260221_0002"
branch_labels = None
depends_on = None
NOW_SQL = "now()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("weekly_plans"):
        op.create_table(
            "weekly_plans",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("current_week", sa.Integer(), nullable=False),
            sa.Column("total_weeks", sa.Integer(), nullable=False),
            sa.Column("plan_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_plans_learner_id ON weekly_plans (learner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_plans_generated_at ON weekly_plans (generated_at)")

    if not inspector.has_table("chapter_progression"):
        op.create_table(
            "chapter_progression",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter", sa.String(length=128), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("best_score", sa.Float(), nullable=False),
            sa.Column("last_score", sa.Float(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("revision_queued", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text(NOW_SQL), nullable=True),
            sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chapter_progression_learner_chapter ON chapter_progression (learner_id, chapter)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_chapter_progression_status ON chapter_progression (status)")


def downgrade() -> None:
    op.drop_index("idx_chapter_progression_status", table_name="chapter_progression")
    op.drop_index("idx_chapter_progression_learner_chapter", table_name="chapter_progression")
    op.drop_table("chapter_progression")

    op.drop_index("idx_weekly_plans_generated_at", table_name="weekly_plans")
    op.drop_index("idx_weekly_plans_learner_id", table_name="weekly_plans")
    op.drop_table("weekly_plans")
