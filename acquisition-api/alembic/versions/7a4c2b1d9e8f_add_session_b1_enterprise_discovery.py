"""add session b1 enterprise discovery

Revision ID: 7a4c2b1d9e8f
Revises: 1f0f5d8e4b3c
Create Date: 2026-09-29 00:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7a4c2b1d9e8f"
down_revision: Union[str, None] = "1f0f5d8e4b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=240), nullable=False),
        sa.Column("normalized_name", sa.String(length=240), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=8), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=False),
        sa.Column(
            "first_discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index("ix_enterprise_created", "enterprise", ["created_at"], unique=False)
    op.create_index("ix_enterprise_domain", "enterprise", ["domain"], unique=False)

    op.create_table(
        "search_result",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=False),
        sa.Column("strategy_version_id", sa.UUID(), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("query_id", sa.UUID(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("result_domain", sa.String(length=255), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "searched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["strategy_channel.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["query_id"], ["strategy_query.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["strategy_id"], ["search_strategy.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"], ["search_strategy_version.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "query_id", "url", name="uq_search_result_provider_query_url"),
    )
    op.create_index("ix_search_result_domain", "search_result", ["result_domain"], unique=False)
    op.create_index(
        "ix_search_result_query_rank", "search_result", ["query_id", "rank"], unique=False
    )

    op.create_table(
        "enterprise_discovery_source",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("enterprise_id", sa.UUID(), nullable=False),
        sa.Column("search_result_id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=False),
        sa.Column("strategy_version", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=48), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("result_url", sa.Text(), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprise.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["search_result_id"], ["search_result.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["search_strategy.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "enterprise_id", "search_result_id", name="uq_discovery_enterprise_search_result"
        ),
    )
    op.create_index(
        "ix_discovery_enterprise",
        "enterprise_discovery_source",
        ["enterprise_id", "discovered_at"],
        unique=False,
    )
    op.create_index(
        "ix_discovery_strategy",
        "enterprise_discovery_source",
        ["strategy_id", "strategy_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_strategy", table_name="enterprise_discovery_source")
    op.drop_index("ix_discovery_enterprise", table_name="enterprise_discovery_source")
    op.drop_table("enterprise_discovery_source")
    op.drop_index("ix_search_result_query_rank", table_name="search_result")
    op.drop_index("ix_search_result_domain", table_name="search_result")
    op.drop_table("search_result")
    op.drop_index("ix_enterprise_domain", table_name="enterprise")
    op.drop_index("ix_enterprise_created", table_name="enterprise")
    op.drop_table("enterprise")
