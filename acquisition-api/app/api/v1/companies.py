"""Candidate enterprise API, aligned with acquisition-web/src/api/company.ts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.common import ApiResponse, PageResult, ok
from app.schemas.company import CompanyStatsOut, EnterpriseOut
from app.schemas.research import ResearchOut
from app.services import company_service, research_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=ApiResponse[PageResult[EnterpriseOut]])
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_name: str | None = None,
    country: str | None = None,
    industry: str | None = None,
    channel: str | None = None,
    profile_id: str | None = None,
    relevance: str | None = None,
    grade: str | None = None,
    db: Session = Depends(get_db),
):
    del profile_id  # Reserved for EnterpriseProfileAnalysis in a later session.
    items, total = company_service.list_companies(
        db,
        page=page,
        page_size=page_size,
        company_name=company_name,
        country=country,
        industry=industry,
        channel=channel,
        relevance=relevance,
        grade=grade,
    )
    return ok(
        PageResult[EnterpriseOut](
            list=company_service.serialize_companies(db, items, include_sources=False),
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/stats", response_model=ApiResponse[CompanyStatsOut])
def get_company_stats(
    profile_id: str | None = None,
    db: Session = Depends(get_db),
):
    del profile_id  # Reserved for EnterpriseProfileAnalysis in a later session.
    return ok(company_service.get_stats(db))


@router.get("/{company_id}/research", response_model=ApiResponse[ResearchOut])
def get_company_research(
    company_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    enterprise = company_service.get_company(db, company_id)
    return ok(research_service.get_research(str(enterprise.id), settings))


@router.get("/{company_id}", response_model=ApiResponse[EnterpriseOut])
def get_company(
    company_id: str,
    profile_id: str | None = None,
    db: Session = Depends(get_db),
):
    del profile_id  # Reserved for EnterpriseProfileAnalysis in a later session.
    enterprise = company_service.get_company(db, company_id)
    return ok(company_service.serialize_companies(db, [enterprise], include_sources=True)[0])
