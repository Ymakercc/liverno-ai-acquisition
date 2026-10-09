"""Add persistent single-enterprise Marketing handoff progress.

Revision ID: f6b8c0d2e4a6
Revises: e5f7a9b1c3d4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6b8c0d2e4a6"
down_revision: Union[str, None] = "e5f7a9b1c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_marketing_handoff",
        sa.Column("enterprise_id", sa.UUID(), sa.ForeignKey("enterprise.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("research_id", sa.String(64)),
        sa.Column("marketing_customer_id", sa.String(64)),
        sa.Column("job_id", sa.String(64)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_id", sa.UUID()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("enterprise_marketing_handoff")
