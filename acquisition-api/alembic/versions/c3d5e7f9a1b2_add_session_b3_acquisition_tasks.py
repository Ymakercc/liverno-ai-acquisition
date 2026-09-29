"""add session b3 acquisition tasks

Revision ID: c3d5e7f9a1b2
Revises: 7a4c2b1d9e8f
Create Date: 2026-09-29 00:20:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d5e7f9a1b2"
down_revision: Union[str, None] = "7a4c2b1d9e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "acquisition_task",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_name", sa.String(length=120), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("max_queries", sa.Integer(), nullable=False),
        sa.Column("results_per_query", sa.Integer(), nullable=False),
        sa.Column("enterprise_target", sa.Integer(), nullable=False),
        sa.Column("queries_executed", sa.Integer(), nullable=False),
        sa.Column("search_results_count", sa.Integer(), nullable=False),
        sa.Column("valid_domains_count", sa.Integer(), nullable=False),
        sa.Column("new_enterprises_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_enterprises_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_acquisition_task_status",
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["search_strategy.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_acquisition_task_status_created",
        "acquisition_task",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_acquisition_task_strategy",
        "acquisition_task",
        ["strategy_id", "created_at"],
        unique=False,
    )
    op.add_column("search_result", sa.Column("acquisition_task_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_search_result_acquisition_task_id",
        "search_result",
        "acquisition_task",
        ["acquisition_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_search_result_acquisition_task",
        "search_result",
        ["acquisition_task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_search_result_acquisition_task", table_name="search_result")
    op.drop_constraint(
        "fk_search_result_acquisition_task_id", "search_result", type_="foreignkey"
    )
    op.drop_column("search_result", "acquisition_task_id")
    op.drop_index("ix_acquisition_task_strategy", table_name="acquisition_task")
    op.drop_index("ix_acquisition_task_status_created", table_name="acquisition_task")
    op.drop_table("acquisition_task")
