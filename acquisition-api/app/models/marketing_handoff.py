"""Persistent progress for one Enterprise's Marketing handoff."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EnterpriseMarketingHandoff(Base):
    __tablename__ = "enterprise_marketing_handoff"

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("enterprise.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="research")
    research_id: Mapped[str | None] = mapped_column(String(64))
    marketing_customer_id: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
