"""Read-only candidate enterprise queries for Session B2."""

import uuid

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models import Enterprise, EnterpriseDiscoverySource, SearchStrategy
from app.schemas.company import (
    CompanyStatsOut,
    DiscoverySummaryOut,
    EnterpriseDiscoverySourceOut,
    EnterpriseOut,
)


def _base_filters(
    *,
    company_name: str | None = None,
    country: str | None = None,
    industry: str | None = None,
    channel: str | None = None,
    relevance: str | None = None,
    grade: str | None = None,
):
    filters = []
    if company_name:
        keyword = f"%{company_name.strip()}%"
        filters.append(
            or_(Enterprise.company_name.ilike(keyword), Enterprise.domain.ilike(keyword))
        )
    if country:
        filters.append(Enterprise.country == country)
    if industry:
        filters.append(Enterprise.industry == industry)
    if channel:
        filters.append(
            Enterprise.discovery_sources.any(EnterpriseDiscoverySource.channel == channel)
        )

    # EnterpriseProfileAnalysis is outside Session B2. Existing enterprises are pending.
    if relevance and relevance != "pending":
        filters.append(false())
    if grade:
        filters.append(false())
    return filters


def list_companies(
    db: Session,
    *,
    page: int,
    page_size: int,
    company_name: str | None = None,
    country: str | None = None,
    industry: str | None = None,
    channel: str | None = None,
    relevance: str | None = None,
    grade: str | None = None,
) -> tuple[list[Enterprise], int]:
    filters = _base_filters(
        company_name=company_name,
        country=country,
        industry=industry,
        channel=channel,
        relevance=relevance,
        grade=grade,
    )
    total = db.scalar(select(func.count()).select_from(Enterprise).where(*filters)) or 0
    items = db.scalars(
        select(Enterprise)
        .where(*filters)
        .options(selectinload(Enterprise.discovery_sources))
        .order_by(Enterprise.first_discovered_at.desc(), Enterprise.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def get_company(db: Session, company_id: str) -> Enterprise:
    try:
        enterprise_id = uuid.UUID(company_id)
    except (TypeError, ValueError):
        raise NotFoundError("候选企业不存在") from None

    enterprise = db.scalar(
        select(Enterprise)
        .where(Enterprise.id == enterprise_id)
        .options(selectinload(Enterprise.discovery_sources))
    )
    if enterprise is None:
        raise NotFoundError("候选企业不存在")
    return enterprise


def get_stats(db: Session) -> CompanyStatsOut:
    total = db.scalar(select(func.count()).select_from(Enterprise)) or 0
    return CompanyStatsOut(total=total, pending=total)


def serialize_companies(
    db: Session, enterprises: list[Enterprise], *, include_sources: bool
) -> list[EnterpriseOut]:
    strategy_ids = {
        source.strategy_id
        for enterprise in enterprises
        for source in enterprise.discovery_sources
    }
    strategy_codes = {
        strategy_id: code
        for strategy_id, code in db.execute(
            select(SearchStrategy.id, SearchStrategy.code).where(SearchStrategy.id.in_(strategy_ids))
        )
    } if strategy_ids else {}

    return [
        _serialize_company(
            enterprise,
            strategy_codes=strategy_codes,
            include_sources=include_sources,
        )
        for enterprise in enterprises
    ]


def _serialize_company(
    enterprise: Enterprise,
    *,
    strategy_codes: dict,
    include_sources: bool,
) -> EnterpriseOut:
    sources = sorted(
        enterprise.discovery_sources,
        key=lambda source: source.discovered_at,
        reverse=True,
    )
    latest = sources[0] if sources else None
    source_items = [
        EnterpriseDiscoverySourceOut(
            id=str(source.id),
            enterprise_id=str(source.enterprise_id),
            strategy_id=str(source.strategy_id),
            strategy_code=strategy_codes.get(source.strategy_id, ""),
            strategy_version=source.strategy_version,
            channel=source.channel,
            query=source.query,
            provider=source.provider,
            result_url=source.result_url,
            discovered_at=source.discovered_at,
        )
        for source in sources
    ]
    summary = DiscoverySummaryOut(
        strategy_count=len({source.strategy_id for source in sources}),
        channels=sorted({source.channel for source in sources}),
        latest_strategy_id=str(latest.strategy_id) if latest else "",
        latest_strategy_code=strategy_codes.get(latest.strategy_id, "") if latest else "",
        latest_discovered_at=latest.discovered_at if latest else None,
    )
    return EnterpriseOut(
        id=str(enterprise.id),
        company_name=enterprise.company_name,
        normalized_name=enterprise.normalized_name,
        domain=enterprise.domain,
        website=enterprise.website,
        country=enterprise.country,
        industry=enterprise.industry,
        first_discovered_at=enterprise.first_discovered_at,
        created_at=enterprise.created_at,
        updated_at=enterprise.updated_at,
        discovery_summary=summary,
        discovery_sources=source_items if include_sources else None,
    )
