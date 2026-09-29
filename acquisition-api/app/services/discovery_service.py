"""Session B1 discovery pipeline: StrategyQuery -> SearchProvider -> Enterprise."""

import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import tldextract
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError, ValidationError
from app.models import (
    AcquisitionTaskSearchResult,
    AcquisitionTaskQueryExecution,
    Enterprise,
    EnterpriseDiscoverySource,
    SearchResult,
    SearchStrategy,
    SearchStrategyVersion,
    StrategyChannel,
    StrategyQuery,
    StrategyQueryExecutionState,
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
LOW_YIELD_RATE = 0.20
LOW_YIELD_RUN_LIMIT = 2
QUERY_COOLDOWN = timedelta(hours=24)


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


def _eligible_queries(
    db: Session, version_id: uuid.UUID
) -> list[tuple[StrategyChannel, StrategyQuery]]:
    rows = _enabled_queries(db, version_id)
    if not rows:
        return []

    query_ids = [query.id for _, query in rows]
    states = {
        state.strategy_query_id: state
        for state in db.scalars(
            select(StrategyQueryExecutionState).where(
                StrategyQueryExecutionState.strategy_query_id.in_(query_ids)
            )
        ).all()
    }
    now = datetime.now(timezone.utc)
    candidates = []
    for channel, query in rows:
        state = states.get(query.id)
        if state and state.status == "exhausted":
            continue
        if (
            state
            and state.status == "cooldown"
            and state.cooldown_until is not None
            and state.cooldown_until > now
        ):
            continue
        candidates.append((channel, query, state))

    candidates.sort(
        key=lambda row: (
            0 if row[2] is None or row[2].last_run_at is None else 1,
            row[2].last_run_at if row[2] and row[2].last_run_at else now,
            row[0].sort_order,
            row[1].sort_order,
            str(row[1].id),
        )
    )
    return [(channel, query) for channel, query, _ in candidates]


def _reserve_query_execution(
    db: Session,
    *,
    acquisition_task_id: uuid.UUID,
    query_id: uuid.UUID,
    requested_limit: int,
) -> AcquisitionTaskQueryExecution | None:
    # The query row is the stable lock target even before its state row exists.
    query = db.scalar(
        select(StrategyQuery).where(StrategyQuery.id == query_id).with_for_update()
    )
    if query is None:
        db.rollback()
        return None

    state = db.scalar(
        select(StrategyQueryExecutionState)
        .where(StrategyQueryExecutionState.strategy_query_id == query_id)
        .with_for_update()
    )
    if state is None:
        state = StrategyQueryExecutionState(strategy_query_id=query_id)
        db.add(state)
        db.flush()

    now = datetime.now(timezone.utc)
    if state.status == "exhausted":
        db.commit()
        return None
    if state.status == "cooldown":
        if state.cooldown_until is not None and state.cooldown_until > now:
            db.commit()
            return None
        state.status = "active"
        state.cooldown_until = None
        state.consecutive_low_yield_runs = 0

    page = state.next_page
    state.next_page += 1
    state.last_run_at = now
    execution = AcquisitionTaskQueryExecution(
        acquisition_task_id=acquisition_task_id,
        strategy_query_id=query_id,
        page=page,
        requested_limit=requested_limit,
        status="running",
        started_at=now,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _search_with_retry(
    db: Session,
    *,
    provider: SearchProvider,
    query: StrategyQuery,
    limit: int,
    page: int,
    execution_id: uuid.UUID | None,
) -> list[ProviderSearchResult]:
    for attempt in range(2):
        try:
            return provider.search(
                query.query_text,
                country_code=query.country_code,
                language=query.language,
                limit=limit,
                page=page,
            )
        except Exception as exc:
            db.rollback()
            if execution_id is None:
                raise
            execution = db.get(AcquisitionTaskQueryExecution, execution_id)
            if execution is None:
                raise
            if attempt == 0:
                execution.retry_count = 1
                db.commit()
                continue
            execution.status = "failed"
            execution.failure_reason = str(exc) or exc.__class__.__name__
            execution.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise
    raise RuntimeError("unreachable provider retry state")


def _complete_query_execution(
    db: Session,
    *,
    execution_id: uuid.UUID,
    provider_returned_count: int,
    search_results_observed_count: int,
    valid_domain_count: int,
    new_enterprises_count: int,
    duplicate_enterprises_count: int,
) -> None:
    execution = db.get(AcquisitionTaskQueryExecution, execution_id)
    if execution is None:
        raise RuntimeError("Query execution disappeared before completion")
    state = db.scalar(
        select(StrategyQueryExecutionState)
        .where(StrategyQueryExecutionState.strategy_query_id == execution.strategy_query_id)
        .with_for_update()
    )
    if state is None:
        raise RuntimeError("Query execution state disappeared before completion")

    execution.provider_returned_count = provider_returned_count
    execution.search_results_observed_count = search_results_observed_count
    execution.valid_domain_count = valid_domain_count
    execution.new_enterprises_count = new_enterprises_count
    execution.duplicate_enterprises_count = duplicate_enterprises_count
    execution.status = "completed"
    execution.finished_at = datetime.now(timezone.utc)

    if provider_returned_count == 0:
        state.status = "exhausted"
        state.cooldown_until = None
    else:
        yield_rate = new_enterprises_count / valid_domain_count if valid_domain_count else 0
        if yield_rate < LOW_YIELD_RATE:
            state.consecutive_low_yield_runs += 1
        else:
            state.consecutive_low_yield_runs = 0
        if state.consecutive_low_yield_runs >= LOW_YIELD_RUN_LIMIT:
            state.status = "cooldown"
            state.cooldown_until = datetime.now(timezone.utc) + QUERY_COOLDOWN
        else:
            state.status = "active"
            state.cooldown_until = None

    db.commit()


def _fail_running_execution(db: Session, execution_id: uuid.UUID, exc: Exception) -> None:
    db.rollback()
    execution = db.get(AcquisitionTaskQueryExecution, execution_id)
    if execution is not None and execution.status == "running":
        execution.status = "failed"
        execution.failure_reason = str(exc) or exc.__class__.__name__
        execution.finished_at = datetime.now(timezone.utc)
        db.commit()


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

    enabled_rows = _enabled_queries(db, version.id)
    if not enabled_rows:
        raise ValidationError("Active SearchStrategy 没有 enabled StrategyQuery")
    query_rows = (
        _eligible_queries(db, version.id)
        if acquisition_task_id is not None
        else enabled_rows[:max_queries]
    )

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

    executed_count = 0
    try:
        for channel, query in query_rows:
            if executed_count >= max_queries:
                break
            if stats["enterprise_inserted_count"] >= enterprise_target:
                break

            execution = None
            page = 1
            if acquisition_task_id is not None:
                execution = _reserve_query_execution(
                    db,
                    acquisition_task_id=acquisition_task_id,
                    query_id=query.id,
                    requested_limit=results_per_query,
                )
                if execution is None:
                    continue
                page = execution.page

            executed_count += 1
            stats["query_texts"].append(query.query_text)
            query_stats = {
                "provider_returned_count": 0,
                "search_results_observed_count": 0,
                "valid_domain_count": 0,
                "new_enterprises_count": 0,
                "duplicate_enterprises_count": 0,
            }

            try:
                provider_results = _search_with_retry(
                    db,
                    provider=provider,
                    query=query,
                    limit=results_per_query,
                    page=page,
                    execution_id=execution.id if execution else None,
                )
                query_stats["provider_returned_count"] = len(provider_results)
                stats["provider_returned_count"] += len(provider_results)

                for item in provider_results:
                    if stats["enterprise_inserted_count"] >= enterprise_target:
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
                    query_stats["search_results_observed_count"] += 1
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
                    query_stats["valid_domain_count"] += 1

                    enterprise, enterprise_created = _get_or_create_enterprise(
                        db,
                        domain=domain,
                        title=item.title,
                        url=item.url,
                    )
                    if enterprise_created:
                        stats["enterprise_inserted_count"] += 1
                        query_stats["new_enterprises_count"] += 1
                    else:
                        stats["enterprise_duplicate_count"] += 1
                        query_stats["duplicate_enterprises_count"] += 1

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

                if execution is not None:
                    _complete_query_execution(
                        db,
                        execution_id=execution.id,
                        **query_stats,
                    )
                else:
                    db.commit()
            except Exception as exc:
                if execution is not None:
                    _fail_running_execution(db, execution.id, exc)
                raise

    except Exception:
        db.rollback()
        raise

    return stats
