"""Session B1 discovery pipeline: StrategyQuery -> SearchProvider -> Enterprise."""

import re
import uuid
from urllib.parse import urlparse

import tldextract
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError, ValidationError
from app.models import (
    AcquisitionTaskSearchResult,
    Enterprise,
    EnterpriseDiscoverySource,
    SearchResult,
    SearchStrategy,
    SearchStrategyVersion,
    StrategyChannel,
    StrategyQuery,
)
from app.providers.base import ProviderSearchResult, SearchProvider

COMPANY_SUFFIX_RE = re.compile(
    r"\b(gmbh|ltd|limited|inc|corp|corporation|llc|ag|s\.?a\.?|srl|bv|nv|plc|co)\b\.?",
    re.IGNORECASE,
)
NON_ENTERPRISE_DOMAINS = {
    "google.com",
    "bing.com",
    "yahoo.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "wikipedia.org",
    "amazon.com",
    "alibaba.com",
    "made-in-china.com",
}
DOMAIN_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)


def _to_uuid(value: str, message: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotFoundError(message) from exc


def extract_main_domain(url: str) -> str | None:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return None
    extracted = DOMAIN_EXTRACTOR(host)
    domain = extracted.top_domain_under_public_suffix
    if not domain:
        return None
    if domain in NON_ENTERPRISE_DOMAINS:
        return None
    return domain


def normalize_company_name(value: str, domain: str) -> str:
    source = value.strip() or domain.split(".")[0]
    source = source.split("|")[0].split(" - ")[0].strip()
    source = COMPANY_SUFFIX_RE.sub("", source)
    normalized = re.sub(r"[^a-z0-9]+", " ", source.lower()).strip()
    return normalized or domain.split(".")[0]


def _display_name(value: str, domain: str) -> str:
    title = value.strip()
    if title:
        return title.split("|")[0].split(" - ")[0].strip()[:240]
    return domain.split(".")[0].replace("-", " ").title()[:240]


def _load_active_strategy(db: Session, strategy_id: str | None) -> SearchStrategy:
    stmt = select(SearchStrategy).where(SearchStrategy.status == "active")
    if strategy_id:
        stmt = stmt.where(SearchStrategy.id == _to_uuid(strategy_id, "搜索策略不存在"))
    stmt = stmt.order_by(SearchStrategy.updated_at.desc()).limit(1)
    strategy = db.scalars(stmt).first()
    if strategy is None:
        raise NotFoundError("没有可执行的 Active SearchStrategy")
    if strategy.current_version_id is None:
        raise ValidationError("Active SearchStrategy 缺少 current_version_id")
    return strategy


def _enabled_queries(db: Session, version_id: uuid.UUID) -> list[tuple[StrategyChannel, StrategyQuery]]:
    stmt = (
        select(StrategyChannel)
        .where(StrategyChannel.version_id == version_id)
        .where(StrategyChannel.enabled.is_(True))
        .options(selectinload(StrategyChannel.queries))
        .order_by(StrategyChannel.sort_order)
    )
    rows: list[tuple[StrategyChannel, StrategyQuery]] = []
    for channel in db.scalars(stmt).all():
        for query in channel.queries:
            if query.enabled and query.query_text.strip():
                rows.append((channel, query))
    return rows


def _get_or_create_search_result(
    db: Session,
    *,
    provider: str,
    strategy: SearchStrategy,
    version: SearchStrategyVersion,
    channel: StrategyChannel,
    query: StrategyQuery,
    item: ProviderSearchResult,
    domain: str | None,
) -> tuple[SearchResult, bool]:
    existing = db.scalars(
        select(SearchResult)
        .where(SearchResult.provider == provider)
        .where(SearchResult.query_id == query.id)
        .where(SearchResult.url == item.url)
    ).first()
    if existing:
        return existing, False

    row = SearchResult(
        provider=provider,
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        channel_id=channel.id,
        query_id=query.id,
        query_text=query.query_text,
        country_code=query.country_code,
        language=query.language,
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        result_domain=domain,
        rank=item.rank,
        raw=item.raw,
    )
    db.add(row)
    db.flush()
    return row, True


def _get_or_create_task_search_result(
    db: Session,
    *,
    acquisition_task_id: uuid.UUID,
    search_result: SearchResult,
) -> tuple[AcquisitionTaskSearchResult, bool]:
    existing = db.scalars(
        select(AcquisitionTaskSearchResult)
        .where(AcquisitionTaskSearchResult.acquisition_task_id == acquisition_task_id)
        .where(AcquisitionTaskSearchResult.search_result_id == search_result.id)
    ).first()
    if existing:
        return existing, False

    link = AcquisitionTaskSearchResult(
        acquisition_task_id=acquisition_task_id,
        search_result_id=search_result.id,
    )
    db.add(link)
    db.flush()
    return link, True


def _get_or_create_enterprise(
    db: Session,
    *,
    domain: str,
    title: str,
    url: str,
) -> tuple[Enterprise, bool]:
    existing = db.scalars(select(Enterprise).where(Enterprise.domain == domain)).first()
    if existing:
        return existing, False

    enterprise = Enterprise(
        company_name=_display_name(title, domain),
        normalized_name=normalize_company_name(title, domain),
        domain=domain,
        website=url,
        country="",
        industry="",
    )
    db.add(enterprise)
    db.flush()
    return enterprise, True


def _get_or_create_discovery_source(
    db: Session,
    *,
    enterprise: Enterprise,
    search_result: SearchResult,
    strategy: SearchStrategy,
    version: SearchStrategyVersion,
    channel: StrategyChannel,
    query: StrategyQuery,
    provider: str,
) -> tuple[EnterpriseDiscoverySource, bool]:
    existing = db.scalars(
        select(EnterpriseDiscoverySource)
        .where(EnterpriseDiscoverySource.enterprise_id == enterprise.id)
        .where(EnterpriseDiscoverySource.search_result_id == search_result.id)
    ).first()
    if existing:
        return existing, False

    source = EnterpriseDiscoverySource(
        enterprise_id=enterprise.id,
        search_result_id=search_result.id,
        strategy_id=strategy.id,
        strategy_version=version.version,
        channel=channel.channel,
        query=query.query_text,
        provider=provider,
        result_url=search_result.url,
    )
    db.add(source)
    db.flush()
    return source, True


def run_discovery(
    db: Session,
    *,
    provider: SearchProvider,
    strategy_id: str | None,
    max_queries: int,
    results_per_query: int,
    enterprise_target: int,
    acquisition_task_id: uuid.UUID | None = None,
) -> dict:
    strategy = _load_active_strategy(db, strategy_id)
    version = db.get(SearchStrategyVersion, strategy.current_version_id)
    if version is None:
        raise ValidationError("Active SearchStrategy 当前版本不存在")

    query_rows = _enabled_queries(db, version.id)[:max_queries]
    if not query_rows:
        raise ValidationError("Active SearchStrategy 没有 enabled StrategyQuery")

    stats = {
        "strategy_id": str(strategy.id),
        "strategy_version": version.version,
        "provider": provider.name,
        "query_texts": [],
        "provider_returned_count": 0,
        "search_result_inserted_count": 0,
        "search_result_existing_count": 0,
        "valid_domain_count": 0,
        "enterprise_inserted_count": 0,
        "enterprise_duplicate_count": 0,
        "discovery_source_inserted_count": 0,
        "discovery_source_existing_count": 0,
    }

    try:
        for channel, query in query_rows:
            if stats["valid_domain_count"] >= enterprise_target:
                break
            stats["query_texts"].append(query.query_text)
            provider_results = provider.search(
                query.query_text,
                country_code=query.country_code,
                language=query.language,
                limit=results_per_query,
            )
            stats["provider_returned_count"] += len(provider_results)

            for item in provider_results:
                if stats["valid_domain_count"] >= enterprise_target:
                    break

                domain = extract_main_domain(item.url)
                search_result, result_created = _get_or_create_search_result(
                    db,
                    provider=provider.name,
                    strategy=strategy,
                    version=version,
                    channel=channel,
                    query=query,
                    item=item,
                    domain=domain,
                )
                if result_created:
                    stats["search_result_inserted_count"] += 1
                else:
                    stats["search_result_existing_count"] += 1

                if acquisition_task_id is not None:
                    _get_or_create_task_search_result(
                        db,
                        acquisition_task_id=acquisition_task_id,
                        search_result=search_result,
                    )

                if not domain:
                    continue
                stats["valid_domain_count"] += 1

                enterprise, enterprise_created = _get_or_create_enterprise(
                    db,
                    domain=domain,
                    title=item.title,
                    url=item.url,
                )
                if enterprise_created:
                    stats["enterprise_inserted_count"] += 1
                else:
                    stats["enterprise_duplicate_count"] += 1

                _, source_created = _get_or_create_discovery_source(
                    db,
                    enterprise=enterprise,
                    search_result=search_result,
                    strategy=strategy,
                    version=version,
                    channel=channel,
                    query=query,
                    provider=provider.name,
                )
                if source_created:
                    stats["discovery_source_inserted_count"] += 1
                else:
                    stats["discovery_source_existing_count"] += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return stats
