"""add task search result history

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2
Create Date: 2026-09-29 00:40:00.000000+00:00
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e6f8a0b2c3"
down_revision: Union[str, None] = "c3d5e7f9a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    task_search_result = op.create_table(
        "acquisition_task_search_result",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("acquisition_task_id", sa.UUID(), nullable=False),
        sa.Column("search_result_id", sa.UUID(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_task_id"], ["acquisition_task.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["search_result_id"], ["search_result.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "acquisition_task_id", "search_result_id", name="uq_task_search_result"
        ),
    )
    op.create_index(
        "ix_task_search_result_task",
        "acquisition_task_search_result",
        ["acquisition_task_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_search_result_result",
        "acquisition_task_search_result",
        ["search_result_id"],
        unique=False,
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id AS search_result_id, acquisition_task_id
            FROM search_result
            WHERE acquisition_task_id IS NOT NULL
            """
        )
    ).mappings()
    op.bulk_insert(
        task_search_result,
        [
            {
                "id": uuid.uuid4(),
                "acquisition_task_id": row["acquisition_task_id"],
                "search_result_id": row["search_result_id"],
            }
            for row in rows
        ],
    )

    op.drop_index("ix_search_result_acquisition_task", table_name="search_result")
    op.drop_constraint(
        "fk_search_result_acquisition_task_id", "search_result", type_="foreignkey"
    )
    op.drop_column("search_result", "acquisition_task_id")


def downgrade() -> None:
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
    op.execute(
        """
        UPDATE search_result AS sr
        SET acquisition_task_id = links.acquisition_task_id
        FROM (
            SELECT DISTINCT ON (search_result_id)
                search_result_id, acquisition_task_id
            FROM acquisition_task_search_result
            ORDER BY search_result_id, observed_at
        ) AS links
        WHERE sr.id = links.search_result_id
        """
    )
    op.drop_index("ix_task_search_result_result", table_name="acquisition_task_search_result")
    op.drop_index("ix_task_search_result_task", table_name="acquisition_task_search_result")
    op.drop_table("acquisition_task_search_result")
