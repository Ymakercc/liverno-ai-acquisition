"""Enterprise discovery models for Session B1."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Enterprise(TimestampMixin, Base):
    __tablename__ = "enterprise"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(240), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    industry: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    discovery_sources = relationship("EnterpriseDiscoverySource", back_populates="enterprise")

    __table_args__ = (
        Index("ix_enterprise_domain", "domain"),
        Index("ix_enterprise_created", "created_at"),
    )


class SearchResult(Base):
    __tablename__ = "search_result"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_strategy.id", ondelete="RESTRICT"), nullable=False
    )
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("search_strategy_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategy_channel.id", ondelete="RESTRICT"), nullable=False
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategy_query.id", ondelete="RESTRICT"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    discovery_sources = relationship("EnterpriseDiscoverySource", back_populates="search_result")

    __table_args__ = (
        UniqueConstraint("provider", "query_id", "url", name="uq_search_result_provider_query_url"),
        Index("ix_search_result_query_rank", "query_id", "rank"),
        Index("ix_search_result_domain", "result_domain"),
    )


class EnterpriseDiscoverySource(Base):
    __tablename__ = "enterprise_discovery_source"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False
    )
    search_result_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_result.id", ondelete="CASCADE"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_strategy.id", ondelete="RESTRICT"), nullable=False
    )
    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    result_url: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    enterprise = relationship("Enterprise", back_populates="discovery_sources")
    search_result = relationship("SearchResult", back_populates="discovery_sources")

    __table_args__ = (
        UniqueConstraint(
            "enterprise_id", "search_result_id", name="uq_discovery_enterprise_search_result"
        ),
        Index("ix_discovery_enterprise", "enterprise_id", "discovered_at"),
        Index("ix_discovery_strategy", "strategy_id", "strategy_version"),
    )
