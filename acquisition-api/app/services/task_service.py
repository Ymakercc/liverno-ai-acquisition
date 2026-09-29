"""Persisted acquisition task orchestration for Session B3."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    AcquisitionTask,
    AcquisitionTaskQueryExecution,
    AcquisitionTaskSearchResult,
    CustomerProfile,
    SearchStrategy,
    SearchStrategyVersion,
    SearchResult,
    StrategyChannel,
    StrategyQuery,
)
from app.providers.base import SearchProvider
from app.schemas.task import AcquisitionTaskCreate, AcquisitionTaskStatsOut
from app.services import discovery_service


def _to_uuid(value: str, message: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotFoundError(message) from exc


def _load_task(db: Session, task_id: str, *, for_update: bool = False) -> AcquisitionTask:
    stmt = select(AcquisitionTask).where(
        AcquisitionTask.id == _to_uuid(task_id, "获客任务不存在")
    )
    if for_update:
        stmt = stmt.with_for_update()
    task = db.scalar(stmt)
    if task is None:
        raise NotFoundError("获客任务不存在")
    return task


def _load_active_strategy(db: Session, strategy_id: str) -> tuple[SearchStrategy, SearchStrategyVersion]:
    strategy = db.get(SearchStrategy, _to_uuid(strategy_id, "搜索策略不存在"))
    if strategy is None:
        raise NotFoundError("搜索策略不存在")
    if strategy.status != "active" or strategy.current_version_id is None:
        raise ValidationError("仅 Active SearchStrategy 可创建或执行获客任务")

    profile = db.get(CustomerProfile, strategy.profile_id)
    if profile is None or not profile.is_enabled:
        raise ValidationError("上游客户画像已暂停，暂不能创建或执行获客任务")

    version = db.get(SearchStrategyVersion, strategy.current_version_id)
    if version is None:
        raise ValidationError("Active SearchStrategy 当前版本不存在")
    if not discovery_service._enabled_queries(db, version.id):
        raise ValidationError("Active SearchStrategy 没有 enabled StrategyQuery")
    return strategy, version


def _task_snapshots(db: Session, task: AcquisitionTask) -> tuple[list[dict], list[str]]:
    version = db.scalar(
        select(SearchStrategyVersion)
        .where(SearchStrategyVersion.strategy_id == task.strategy_id)
        .where(SearchStrategyVersion.version == task.strategy_version)
    )
    if version is None:
        return [], []

    execution_rows = db.execute(
        select(AcquisitionTaskQueryExecution, StrategyQuery, StrategyChannel)
        .join(
            StrategyQuery,
            StrategyQuery.id == AcquisitionTaskQueryExecution.strategy_query_id,
        )
        .join(StrategyChannel, StrategyChannel.id == StrategyQuery.channel_id)
        .where(AcquisitionTaskQueryExecution.acquisition_task_id == task.id)
        .order_by(AcquisitionTaskQueryExecution.started_at, StrategyQuery.id)
    ).all()
    selected = (
        [(channel, query, execution) for execution, query, channel in execution_rows]
        if execution_rows
        else [
            (channel, query, None)
            for channel, query in discovery_service._enabled_queries(db, version.id)[: task.max_queries]
        ]
    )
    snapshots: list[dict] = []
    countries: set[str] = set()
    by_channel: dict[uuid.UUID, dict] = {}
    for channel, query, execution in selected:
        snapshot = by_channel.get(channel.id)
        if snapshot is None:
            snapshot = {
                "channel": channel.channel,
                "queries": [],
                "target_countries": list(channel.target_countries or []),
                "raw_discovered_count": 0,
            }
            by_channel[channel.id] = snapshot
            snapshots.append(snapshot)
            countries.update(channel.target_countries or [])
        snapshot["queries"].append(query.query_text)
        if execution is not None:
            snapshot["raw_discovered_count"] += execution.provider_returned_count
    return snapshots, sorted(countries)


def _task_search_results(db: Session, task_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(AcquisitionTaskSearchResult, SearchResult)
        .join(SearchResult, SearchResult.id == AcquisitionTaskSearchResult.search_result_id)
        .where(AcquisitionTaskSearchResult.acquisition_task_id == task_id)
        .order_by(AcquisitionTaskSearchResult.observed_at, SearchResult.rank)
    ).all()
    return [
        {
            "id": str(result.id),
            "title": result.title,
            "url": result.url,
            "result_domain": result.result_domain,
            "query_text": result.query_text,
            "rank": result.rank,
            "observed_at": link.observed_at,
        }
        for link, result in rows
    ]


def _task_query_executions(db: Session, task_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(AcquisitionTaskQueryExecution, StrategyQuery)
        .join(
            StrategyQuery,
            StrategyQuery.id == AcquisitionTaskQueryExecution.strategy_query_id,
        )
        .where(AcquisitionTaskQueryExecution.acquisition_task_id == task_id)
        .order_by(AcquisitionTaskQueryExecution.started_at, AcquisitionTaskQueryExecution.id)
    ).all()
    return [
        {
            "id": str(execution.id),
            "strategy_query_id": str(execution.strategy_query_id),
            "query_text": query.query_text,
            "page": execution.page,
            "requested_limit": execution.requested_limit,
            "provider_returned_count": execution.provider_returned_count,
            "search_results_observed_count": execution.search_results_observed_count,
            "valid_domain_count": execution.valid_domain_count,
            "new_enterprises_count": execution.new_enterprises_count,
            "duplicate_enterprises_count": execution.duplicate_enterprises_count,
            "status": execution.status,
            "retry_count": execution.retry_count,
            "failure_reason": execution.failure_reason,
            "started_at": execution.started_at,
            "finished_at": execution.finished_at,
        }
        for execution, query in rows
    ]


def _task_execution_totals(db: Session, task_id: uuid.UUID) -> dict[str, int]:
    executions = db.scalars(
        select(AcquisitionTaskQueryExecution).where(
            AcquisitionTaskQueryExecution.acquisition_task_id == task_id,
            AcquisitionTaskQueryExecution.status == "completed",
        )
    ).all()
    return {
        "queries_executed": len(executions),
        "search_results_count": sum(row.search_results_observed_count for row in executions),
        "valid_domains_count": sum(row.valid_domain_count for row in executions),
        "new_enterprises_count": sum(row.new_enterprises_count for row in executions),
        "duplicate_enterprises_count": sum(
            row.duplicate_enterprises_count for row in executions
        ),
    }


def build_task_view(db: Session, task: AcquisitionTask, *, include_results: bool = False) -> dict:
    strategy = db.get(SearchStrategy, task.strategy_id)
    profile = db.get(CustomerProfile, strategy.profile_id) if strategy else None
    snapshots, countries = _task_snapshots(db, task)
    linked_result_count = db.scalar(
        select(func.count())
        .select_from(AcquisitionTaskSearchResult)
        .where(AcquisitionTaskSearchResult.acquisition_task_id == task.id)
    ) or 0
    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "profile_id": str(strategy.profile_id) if strategy else "",
        "profile_name": profile.profile_name if profile else "",
        "strategy_id": str(task.strategy_id),
        "strategy_code": strategy.code if strategy else "",
        "strategy_version": task.strategy_version,
        "status": task.status,
        "max_queries": task.max_queries,
        "results_per_query": task.results_per_query,
        "enterprise_target": task.enterprise_target,
        "queries_executed": task.queries_executed,
        "search_results_count": linked_result_count,
        "valid_domains_count": task.valid_domains_count,
        "new_enterprises_count": task.new_enterprises_count,
        "duplicate_enterprises_count": task.duplicate_enterprises_count,
        "channel_snapshots": snapshots,
        "query_count": sum(len(snapshot["queries"]) for snapshot in snapshots),
        "target_countries": countries,
        "search_results": _task_search_results(db, task.id) if include_results else [],
        "query_executions": _task_query_executions(db, task.id) if include_results else [],
        "failure_reason": task.failure_reason,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "updated_at": task.updated_at,
    }


def list_tasks(
    db: Session,
    *,
    page: int,
    page_size: int,
    task_name: str | None = None,
    profile_name: str | None = None,
    strategy_id: str | None = None,
    status: str | None = None,
) -> tuple[list[dict], int]:
    stmt = (
        select(AcquisitionTask)
        .join(SearchStrategy, SearchStrategy.id == AcquisitionTask.strategy_id)
        .join(CustomerProfile, CustomerProfile.id == SearchStrategy.profile_id)
    )
    conditions = []
    if task_name:
        conditions.append(AcquisitionTask.task_name.ilike(f"%{task_name.strip()}%"))
    if profile_name:
        conditions.append(CustomerProfile.profile_name.ilike(f"%{profile_name.strip()}%"))
    if strategy_id:
        keyword = f"%{strategy_id.strip()}%"
        conditions.append(
            or_(
                SearchStrategy.code.ilike(keyword),
                cast(SearchStrategy.id, String).ilike(keyword),
            )
        )
    if status:
        conditions.append(AcquisitionTask.status == status)

    stmt = stmt.where(*conditions)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    tasks = db.scalars(
        stmt.order_by(AcquisitionTask.created_at.desc(), AcquisitionTask.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [build_task_view(db, task) for task in tasks], total


def get_task_view(db: Session, task_id: str) -> dict:
    return build_task_view(db, _load_task(db, task_id), include_results=True)


def get_task_stats(db: Session) -> AcquisitionTaskStatsOut:
    rows = db.execute(
        select(AcquisitionTask.status, func.count()).group_by(AcquisitionTask.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    return AcquisitionTaskStatsOut(
        total=sum(counts.values()),
        pending=counts.get("pending", 0),
        running=counts.get("running", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
    )


def create_task(db: Session, payload: AcquisitionTaskCreate) -> dict:
    strategy, version = _load_active_strategy(db, payload.strategy_id)
    task = AcquisitionTask(
        task_name=payload.task_name.strip(),
        strategy_id=strategy.id,
        strategy_version=version.version,
        status="pending",
        max_queries=payload.max_queries,
        results_per_query=payload.results_per_query,
        enterprise_target=payload.enterprise_target,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return build_task_view(db, task)


def run_task(db: Session, task_id: str, provider: SearchProvider) -> dict:
    task = _load_task(db, task_id, for_update=True)
    if task.status != "pending":
        raise ConflictError("仅 pending 获客任务可以执行", code="TASK_NOT_RUNNABLE")

    strategy, _ = _load_active_strategy(db, str(task.strategy_id))
    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    task.finished_at = None
    task.failure_reason = None
    db.commit()

    try:
        discovery_service.run_discovery(
            db,
            provider=provider,
            strategy_id=str(strategy.id),
            max_queries=task.max_queries,
            results_per_query=task.results_per_query,
            enterprise_target=task.enterprise_target,
            acquisition_task_id=task.id,
        )
    except Exception as exc:
        db.rollback()
        failed = _load_task(db, task_id)
        failed.status = "failed"
        failed.finished_at = datetime.now(timezone.utc)
        failed.failure_reason = str(exc) or exc.__class__.__name__
        db.commit()
        db.refresh(failed)
        return build_task_view(db, failed, include_results=True)

    totals = _task_execution_totals(db, task.id)
    completed = _load_task(db, task_id)
    completed.status = "completed"
    completed.finished_at = datetime.now(timezone.utc)
    completed.queries_executed = totals["queries_executed"]
    completed.search_results_count = totals["search_results_count"]
    completed.valid_domains_count = totals["valid_domains_count"]
    completed.new_enterprises_count = totals["new_enterprises_count"]
    completed.duplicate_enterprises_count = totals["duplicate_enterprises_count"]
    db.commit()
    db.refresh(completed)
    return build_task_view(db, completed, include_results=True)
