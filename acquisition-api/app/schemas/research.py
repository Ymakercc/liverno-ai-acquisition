"""Read-only, public-safe subset of Marketing Research."""

from html import unescape

from pydantic import BaseModel, Field, field_validator


class ApolloCompanyOut(BaseModel):
    apollo_name: str | None = None
    domain: str | None = None
    match_score: int | None = None
    country: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    linkedin_url: str | None = None


class ContactSummaryOut(BaseModel):
    title: str | None = None
    has_email: bool = False
    email_status: str | None = None


class WebsiteSignalsOut(BaseModel):
    meanWellMentioned: bool = False
    matchedTerms: list[str] = Field(default_factory=list)
    directFit: bool = False


class WebsiteResearchOut(BaseModel):
    status: str = "not_started"
    final_url: str = ""
    title: str = ""
    description: str = ""
    signals: WebsiteSignalsOut = Field(default_factory=WebsiteSignalsOut)

    @field_validator("title", "description")
    @classmethod
    def decode_entities(cls, value: str) -> str:
        return unescape(value)


class RecommendedProductOut(BaseModel):
    name: str = ""
    reason: str = ""


class QualificationOut(BaseModel):
    status: str = "not_started"
    reason: str = ""
    reason_code: str = ""
    customer_profile: str = ""
    recommended_products: list[RecommendedProductOut] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    failure_reason: str = ""


class ResearchOut(BaseModel):
    status: str
    company: ApolloCompanyOut | None = None
    contacts: list[ContactSummaryOut] = Field(default_factory=list)
    website_research: WebsiteResearchOut = Field(default_factory=WebsiteResearchOut)
    qualification: QualificationOut = Field(default_factory=QualificationOut)
