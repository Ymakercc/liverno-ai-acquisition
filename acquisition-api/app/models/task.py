"""Minimal persisted acquisition task for Session B3."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class AcquisitionTask(TimestampMixin, Base):
    __tablename__ = "acquisition_task"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_strategy.id", ondelete="RESTRICT"), nullable=False
    )
    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    max_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    results_per_query: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    enterprise_target: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    queries_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    search_results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_domains_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_enterprises_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_enterprises_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    strategy = relationship("SearchStrategy")
    search_result_links = relationship(
        "AcquisitionTaskSearchResult",
        back_populates="acquisition_task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_acquisition_task_status",
        ),
        Index("ix_acquisition_task_status_created", "status", "created_at"),
        Index("ix_acquisition_task_strategy", "strategy_id", "created_at"),
    )


class AcquisitionTaskSearchResult(Base):
    __tablename__ = "acquisition_task_search_result"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    acquisition_task_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("acquisition_task.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_result_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_result.id", ondelete="CASCADE"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    acquisition_task = relationship("AcquisitionTask", back_populates="search_result_links")
    search_result = relationship("SearchResult", back_populates="task_links")

    __table_args__ = (
        UniqueConstraint(
            "acquisition_task_id",
            "search_result_id",
            name="uq_task_search_result",
        ),
        Index("ix_task_search_result_task", "acquisition_task_id", "observed_at"),
        Index("ix_task_search_result_result", "search_result_id"),
    )
