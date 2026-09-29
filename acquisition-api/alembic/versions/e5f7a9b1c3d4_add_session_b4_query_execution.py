"""add session b4 query execution state and history

Revision ID: e5f7a9b1c3d4
Revises: d4e6f8a0b2c3
Create Date: 2026-09-29 02:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f7a9b1c3d4"
down_revision: Union[str, None] = "d4e6f8a0b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_query_execution_state",
        sa.Column("strategy_query_id", sa.UUID(), nullable=False),
        sa.Column("next_page", sa.Integer(), nullable=False),
        sa.Column("consecutive_low_yield_runs", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active','cooldown','exhausted')",
            name="ck_query_execution_state_status",
        ),
        sa.CheckConstraint("next_page >= 1", name="ck_query_execution_state_next_page"),
        sa.ForeignKeyConstraint(
            ["strategy_query_id"], ["strategy_query.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("strategy_query_id"),
    )

    op.create_table(
        "acquisition_task_query_execution",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("acquisition_task_id", sa.UUID(), nullable=False),
        sa.Column("strategy_query_id", sa.UUID(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("provider_returned_count", sa.Integer(), nullable=False),
        sa.Column("search_results_observed_count", sa.Integer(), nullable=False),
        sa.Column("valid_domain_count", sa.Integer(), nullable=False),
        sa.Column("new_enterprises_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_enterprises_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','failed')",
            name="ck_task_query_execution_status",
        ),
        sa.CheckConstraint("page >= 1", name="ck_task_query_execution_page"),
        sa.CheckConstraint(
            "retry_count BETWEEN 0 AND 1",
            name="ck_task_query_execution_retry_count",
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_task_id"], ["acquisition_task.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["strategy_query_id"], ["strategy_query.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_query_id",
            "page",
            name="uq_task_query_execution_query_page",
        ),
    )
    op.create_index(
        "ix_task_query_execution_task",
        "acquisition_task_query_execution",
        ["acquisition_task_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_query_execution_query",
        "acquisition_task_query_execution",
        ["strategy_query_id", "started_at"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO strategy_query_execution_state (
            strategy_query_id,
            next_page,
            consecutive_low_yield_runs,
            status
        )
        SELECT id, 1, 0, 'active'
        FROM strategy_query
        WHERE enabled IS TRUE
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_query_execution_query",
        table_name="acquisition_task_query_execution",
    )
    op.drop_index(
        "ix_task_query_execution_task",
        table_name="acquisition_task_query_execution",
    )
    op.drop_table("acquisition_task_query_execution")
    op.drop_table("strategy_query_execution_state")
