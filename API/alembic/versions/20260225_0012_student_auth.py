"""add student_auth for login/signup

Revision ID: 20260225_0012
Revises: 20260222_0011
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260225_0012"
down_revision = "20260222_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_auth",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("username", name="uq_student_auth_username"),
        sa.UniqueConstraint("learner_id", name="uq_student_auth_learner_id"),
    )
    op.create_index("idx_student_auth_username", "student_auth", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_student_auth_username", table_name="student_auth")
    op.drop_table("student_auth")
