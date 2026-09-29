"""客户画像 Schema，字段与 acquisition-web/src/types/profile.ts 严格一致。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProfilePriority = Literal["high", "medium", "low"]


class ProfilePayload(BaseModel):
    """新建 / 编辑提交体（不含 id 与时间戳）。"""

    profile_name: str = Field(min_length=2, max_length=50)
    target_industries: list[str] = Field(default_factory=list)
    target_regions: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)
    company_size: str = "any"
    product_lines: list[str] = Field(default_factory=list)
    application_scenarios: list[str] = Field(default_factory=list)
    required_signals: list[str] = Field(default_factory=list)
    exclude_signals: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    daily_quota: int = Field(ge=1, le=1000)
    priority: ProfilePriority = "medium"
    is_enabled: bool = True

    @field_validator("profile_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("画像名称至少 2 个字符")
        return cleaned

    @field_validator(
        "target_industries",
        "target_regions",
        "target_countries",
        "company_types",
        "product_lines",
        "application_scenarios",
        "required_signals",
        "exclude_signals",
        "target_roles",
    )
    @classmethod
    def _clean_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class CustomerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_name: str
    target_industries: list[str]
    target_regions: list[str]
    target_countries: list[str]
    company_types: list[str]
    company_size: str
    product_lines: list[str]
    application_scenarios: list[str]
    required_signals: list[str]
    exclude_signals: list[str]
    target_roles: list[str]
    daily_quota: int
    priority: ProfilePriority
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    code: str | None = None


class ProfileStatusPayload(BaseModel):
    is_enabled: bool
