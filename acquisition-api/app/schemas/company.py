"""Candidate enterprise API schemas for Session B2."""

from datetime import datetime

from pydantic import BaseModel, Field


class DiscoverySummaryOut(BaseModel):
    strategy_count: int = 0
    channels: list[str] = Field(default_factory=list)
    latest_strategy_id: str = ""
    latest_strategy_code: str = ""
    latest_discovered_at: datetime | None = None


class EnterpriseDiscoverySourceOut(BaseModel):
    id: str
    enterprise_id: str
    strategy_id: str
    strategy_code: str
    strategy_version: int
    channel: str
    query: str
    provider: str
    result_url: str
    discovered_at: datetime


class EnterpriseOut(BaseModel):
    id: str
    company_name: str
    normalized_name: str
    domain: str
    website: str | None = None
    country: str
    industry: str
    first_discovered_at: datetime
    created_at: datetime
    updated_at: datetime
    analysis: None = None
    discovery_summary: DiscoverySummaryOut
    discovery_sources: list[EnterpriseDiscoverySourceOut] | None = None
    analysis_profiles: list[dict[str, str]] = Field(default_factory=list)


class CompanyStatsOut(BaseModel):
    total: int = 0
    relevant: int = 0
    not_relevant: int = 0
    pending: int = 0
