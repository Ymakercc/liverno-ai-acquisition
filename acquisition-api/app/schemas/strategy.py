"""搜索策略 Schema，字段与 acquisition-web/src/types/strategy.ts 严格一致。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StrategyStatus = Literal["draft", "active", "paused"]


class SearchQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query_text: str
    country_code: str | None = None
    language: str | None = None
    enabled: bool = True


class ChannelSearchStrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    enabled: bool = True
    queries: list[SearchQueryOut] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    strategy_summary: str | None = None


class SearchStrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    profile_name: str
    profile_enabled: bool | None = None
    status: StrategyStatus
    version: int
    base_version: int | None = None
    channel_strategies: list[ChannelSearchStrategyOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    code: str | None = None


# ---------- 入参 ----------


class SearchQueryIn(BaseModel):
    id: str | None = None
    query_text: str
    country_code: str | None = None
    language: str | None = None
    enabled: bool = True


class ChannelSearchStrategyIn(BaseModel):
    channel: str
    enabled: bool = True
    queries: list[SearchQueryIn] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    strategy_summary: str | None = None

    @field_validator("queries")
    @classmethod
    def _clean_queries(cls, value: list[SearchQueryIn]) -> list[SearchQueryIn]:
        return [q for q in value if q.query_text and q.query_text.strip()]


class StrategyGeneratePayload(BaseModel):
    profile_id: str


class StrategyUpdatePayload(BaseModel):
    """保存提交体。

    version      本次要落库的版本号（重新生成预览为 base_version + 1）
    base_version 乐观锁基准：本次编辑所基于的服务端版本
    """

    channel_strategies: list[ChannelSearchStrategyIn] = Field(default_factory=list)
    status: StrategyStatus
    version: int
    base_version: int


class StrategyStatusPayload(BaseModel):
    status: StrategyStatus


class StrategyStats(BaseModel):
    total: int = 0
    active: int = 0
    draft: int = 0
    paused: int = 0
