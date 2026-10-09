"""Public-safe progress for the backend Marketing handoff."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MarketingHandoffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enterprise_id: str
    status: str
    stage: str
    research_id: str | None = None
    marketing_customer_id: str | None = None
    job_id: str | None = None
    failure_code: str | None = None
    attempt_count: int = 0
    updated_at: datetime | None = None
