"""add search strategy current version fk

Revision ID: 1f0f5d8e4b3c
Revises: 832a544854e6
Create Date: 2026-09-29 00:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "1f0f5d8e4b3c"
down_revision: Union[str, None] = "832a544854e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_search_strategy_current_version_id_search_strategy_version",
        "search_strategy",
        "search_strategy_version",
        ["current_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_search_strategy_current_version_id_search_strategy_version",
        "search_strategy",
        type_="foreignkey",
    )
