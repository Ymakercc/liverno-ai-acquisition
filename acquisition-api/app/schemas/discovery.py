"""Schemas for the Session B1 search discovery runner."""

from pydantic import BaseModel, Field


class DiscoveryRunPayload(BaseModel):
    strategy_id: str | None = None
    max_queries: int = Field(default=1, ge=1, le=20)
    results_per_query: int = Field(default=5, ge=1, le=50)
    enterprise_target: int = Field(default=5, ge=1, le=100)


class DiscoveryRunResult(BaseModel):
    strategy_id: str
    strategy_version: int
    provider: str
    query_texts: list[str] = Field(default_factory=list)
    provider_returned_count: int = 0
    search_result_inserted_count: int = 0
    search_result_existing_count: int = 0
    valid_domain_count: int = 0
    enterprise_inserted_count: int = 0
    enterprise_duplicate_count: int = 0
    discovery_source_inserted_count: int = 0
    discovery_source_existing_count: int = 0


class EnterpriseSummary(BaseModel):
    id: str
    company_name: str
    normalized_name: str
    domain: str
    website: str | None = None
    country: str
    industry: str
