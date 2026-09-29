"""策略生成器抽象。

AI 供应商调用必须封装在 Generator 内，禁止散落到 Service。
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field, field_validator

from app.models import CustomerProfile


class GeneratedQuery(BaseModel):
    query_text: str
    country_code: str | None = None
    # ISO 639-1，由 AI 按场景判断；禁止按国家硬推导，允许同国多语言
    language: str | None = None
    enabled: bool = True
    sort_order: int = 0

    @field_validator("query_text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("query_text 不能为空")
        return cleaned


class GeneratedChannel(BaseModel):
    channel: str
    enabled: bool = True
    target_countries: list[str] = Field(default_factory=list)
    strategy_summary: str = ""
    queries: list[GeneratedQuery] = Field(default_factory=list)

    @field_validator("channel")
    @classmethod
    def _channel_required(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("channel 不能为空")
        return cleaned


class GeneratedStrategy(BaseModel):
    """AI 输出的结构化结果，写库前必须通过本模型校验。"""

    channels: list[GeneratedChannel] = Field(default_factory=list)

    @field_validator("channels")
    @classmethod
    def _at_least_one_query(cls, value: list[GeneratedChannel]) -> list[GeneratedChannel]:
        if not value:
            raise ValueError("AI 未返回任何渠道")
        if not any(channel.queries for channel in value):
            raise ValueError("AI 返回的渠道均无有效 Query")
        return value


class StrategyGenerator(ABC):
    @abstractmethod
    def generate(self, profile: CustomerProfile) -> GeneratedStrategy:
        """按画像生成搜索策略。失败必须抛异常，不得返回半成品。"""
        raise NotImplementedError
