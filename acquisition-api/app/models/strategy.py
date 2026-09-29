"""搜索策略：逻辑策略 / 版本 / 渠道 / Query 四张表。

冻结规则：
  1. 一个 Profile 一套逻辑 SearchStrategy（profile_id UNIQUE）
  2. regenerate 创建新 Draft Version，不改 current_version_id、不降 strategy.status
  3. 只有显式 Activate 才切换 current_version_id 并置 status=active（同事务）
  4. 全新 Strategy 可以是 draft，current_version_id 允许为空
"""

import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

STRATEGY_STATUSES = ("draft", "active", "paused")
VERSION_SOURCES = ("ai_generate", "ai_regenerate", "manual_edit")


class SearchStrategy(TimestampMixin, Base):
    __tablename__ = "search_strategy"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customer_profile.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("search_strategy_version.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    profile = relationship("CustomerProfile", back_populates="strategy")
    versions = relationship(
        "SearchStrategyVersion",
        back_populates="strategy",
        cascade="all, delete-orphan",
        foreign_keys="SearchStrategyVersion.strategy_id",
        order_by="SearchStrategyVersion.version",
    )
    current_version = relationship(
        "SearchStrategyVersion", foreign_keys=[current_version_id], post_update=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('draft','active','paused')", name="ck_strategy_status"),
        Index("ix_strategy_status_updated", "status", "updated_at"),
    )


class SearchStrategyVersion(TimestampMixin, Base):
    """不可变版本快照。is_committed=False 表示尚未被用户保存确认。"""

    __tablename__ = "search_strategy_version"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_strategy.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="ai_generate")
    is_committed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    strategy = relationship("SearchStrategy", back_populates="versions", foreign_keys=[strategy_id])
    channels = relationship(
        "StrategyChannel",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="StrategyChannel.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_version_strategy_version"),
        CheckConstraint(
            "source IN ('ai_generate','ai_regenerate','manual_edit')", name="ck_version_source"
        ),
        Index("ix_version_strategy", "strategy_id", "version"),
    )


class StrategyChannel(Base):
    __tablename__ = "strategy_channel"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("search_strategy_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_countries: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    strategy_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version = relationship("SearchStrategyVersion", back_populates="channels")
    queries = relationship(
        "StrategyQuery",
        back_populates="channel_ref",
        cascade="all, delete-orphan",
        order_by="StrategyQuery.sort_order",
    )

    __table_args__ = (UniqueConstraint("version_id", "channel", name="uq_channel_version_channel"),)


class StrategyQuery(Base):
    __tablename__ = "strategy_query"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategy_channel.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    channel_ref = relationship("StrategyChannel", back_populates="queries")

    __table_args__ = (Index("ix_query_channel", "channel_id", "sort_order"),)
