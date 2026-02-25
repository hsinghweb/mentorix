"""add onboarding_diagnostic_score to learner_profile

Revision ID: 20260225_0014
Revises: 20260225_0013
Create Date: 2026-02-25

"""

from alembic import op
import sqlalchemy as sa


revision = "20260225_0014"
down_revision = "20260225_0013"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learner_profile"):
        return
    if not _has_column(inspector, "learner_profile", "onboarding_diagnostic_score"):
        op.add_column(
            "learner_profile",
            sa.Column("onboarding_diagnostic_score", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learner_profile"):
        return
    if _has_column(inspector, "learner_profile", "onboarding_diagnostic_score"):
        op.drop_column("learner_profile", "onboarding_diagnostic_score")
