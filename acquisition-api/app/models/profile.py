"""客户画像。

字段与前端契约 acquisition-web/src/types/profile.ts 一致。
不保存 search_keywords —— 搜索内容属于 SearchStrategy。
"""

import uuid

from sqlalchemy import ARRAY, Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

PRIORITIES = ("high", "medium", "low")


class CustomerProfile(TimestampMixin, Base):
    __tablename__ = "customer_profile"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    profile_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    target_industries: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    target_regions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    target_countries: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    company_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    company_size: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    product_lines: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    application_scenarios: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    required_signals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    exclude_signals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    daily_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    strategy = relationship(
        "SearchStrategy", back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("daily_quota BETWEEN 1 AND 1000", name="ck_profile_daily_quota"),
        CheckConstraint(
            "priority IN ('high','medium','low')", name="ck_profile_priority"
        ),
        Index("ix_profile_enabled_updated", "is_enabled", "updated_at"),
        Index("ix_profile_industries", "target_industries", postgresql_using="gin"),
        Index("ix_profile_countries", "target_countries", postgresql_using="gin"),
    )
