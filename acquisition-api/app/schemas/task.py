"""Acquisition task API schemas for Session B3."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskChannelSnapshotOut(BaseModel):
    channel: str
    queries: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    raw_discovered_count: int = 0


class AcquisitionTaskCreate(BaseModel):
    task_name: str = Field(min_length=2, max_length=120)
    strategy_id: str
    max_queries: int = Field(default=3, ge=1, le=5)
    results_per_query: int = Field(default=10, ge=1, le=20)
    enterprise_target: int = Field(default=30, ge=1, le=50)


class TaskSearchResultOut(BaseModel):
    id: str
    title: str
    url: str
    result_domain: str | None = None
    query_text: str
    rank: int
    observed_at: datetime


class AcquisitionTaskOut(BaseModel):
    id: str
    task_name: str
    profile_id: str
    profile_name: str
    strategy_id: str
    strategy_code: str
    strategy_version: int
    status: str

    max_queries: int
    results_per_query: int
    enterprise_target: int
    queries_executed: int
    search_results_count: int
    valid_domains_count: int
    new_enterprises_count: int
    duplicate_enterprises_count: int

    channel_snapshots: list[TaskChannelSnapshotOut] = Field(default_factory=list)
    query_count: int = 0
    target_countries: list[str] = Field(default_factory=list)
    search_results: list[TaskSearchResultOut] = Field(default_factory=list)

    failure_reason: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class AcquisitionTaskStatsOut(BaseModel):
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
