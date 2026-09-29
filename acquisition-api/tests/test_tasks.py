"""Acquisition task orchestration tests."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_search_provider
from app.generators.base import GeneratedChannel, GeneratedQuery, GeneratedStrategy
from app.main import app
from app.models import (
    AcquisitionTask,
    AcquisitionTaskQueryExecution,
    AcquisitionTaskSearchResult,
    Enterprise,
    SearchResult,
    StrategyQuery,
    StrategyQueryExecutionState,
)
from app.providers.base import ProviderSearchResult
from tests.test_discovery import FakeSearchProvider, _create_active_strategy


class FailingSearchProvider:
    name = "failing-provider"

    def search(self, query, *, country_code, language, limit, page):
        raise RuntimeError("provider unavailable")


class RecordingProvider:
    name = "recording-provider"

    def __init__(self, resolver, *, failures=0):
        self.resolver = resolver
        self.failures = failures
        self.calls = []

    def search(self, query, *, country_code, language, limit, page):
        self.calls.append({"query": query, "limit": limit, "page": page})
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary provider failure")
        return self.resolver(query, page, limit)


def _result(domain: str, *, page: int = 1, rank: int = 1) -> ProviderSearchResult:
    return ProviderSearchResult(
        title=domain,
        url=f"https://{domain}/page-{page}/result-{rank}",
        snippet="candidate enterprise",
        rank=rank,
        raw={"position": rank},
    )


def _set_queries(fake_generator, query_texts):
    fake_generator.strategy = GeneratedStrategy(
        channels=[
            GeneratedChannel(
                channel="google",
                enabled=True,
                target_countries=["DE"],
                strategy_summary="B4 deterministic queries",
                queries=[
                    GeneratedQuery(
                        query_text=query_text,
                        country_code="DE",
                        language="de",
                        enabled=True,
                        sort_order=index,
                    )
                    for index, query_text in enumerate(query_texts)
                ],
            )
        ]
    )


def _seed_enterprises(db_session, domains):
    for domain in domains:
        db_session.add(
            Enterprise(
                company_name=domain,
                normalized_name=domain,
                domain=domain,
                website=f"https://{domain}",
                country="",
                industry="",
            )
        )
    db_session.commit()


def _task_payload(strategy_id: str, **overrides) -> dict:
    payload = {
        "task_name": "B3 测试获客任务",
        "strategy_id": strategy_id,
        "max_queries": 1,
        "results_per_query": 3,
        "enterprise_target": 5,
    }
    payload.update(overrides)
    return payload


def test_create_task_is_pending_and_uses_strategy_profile(client, db_session):
    strategy = _create_active_strategy(client)

    response = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    )

    assert response.status_code == 200
    task = response.json()["data"]
    assert task["status"] == "pending"
    assert task["profile_id"] == strategy["profile_id"]
    assert task["profile_name"] == strategy["profile_name"]
    assert task["strategy_code"] == strategy["code"]
    assert task["strategy_version"] == strategy["version"]
    assert task["max_queries"] == 1
    assert db_session.scalar(select(func.count()).select_from(AcquisitionTask)) == 1


def test_inactive_strategy_cannot_create_task(client):
    strategy = _create_active_strategy(client)
    paused = client.patch(
        f"/liver_api/v1/search-strategies/{strategy['id']}/status",
        json={"status": "paused"},
    )
    assert paused.status_code == 200

    response = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_task_cannot_run_after_strategy_is_paused(client, db_session):
    strategy = _create_active_strategy(client)
    created = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    ).json()["data"]
    client.patch(
        f"/liver_api/v1/search-strategies/{strategy['id']}/status",
        json={"status": "paused"},
    )

    response = client.post(f"/liver_api/v1/acquisition-tasks/{created['id']}/run")

    assert response.status_code == 400
    db_session.expire_all()
    assert db_session.get(AcquisitionTask, created["id"]).status == "pending"


def test_pending_task_runs_discovery_and_persists_stats_and_trace(client, db_session):
    provider = FakeSearchProvider()
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    created = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    ).json()["data"]

    response = client.post(f"/liver_api/v1/acquisition-tasks/{created['id']}/run")

    assert response.status_code == 200
    task = response.json()["data"]
    assert task["status"] == "completed"
    assert task["queries_executed"] == 1
    assert task["search_results_count"] == 3
    assert task["valid_domains_count"] == 2
    assert task["new_enterprises_count"] == 2
    assert task["duplicate_enterprises_count"] == 0
    assert task["started_at"] is not None
    assert task["finished_at"] is not None
    assert provider.calls[0]["limit"] == 3

    linked = db_session.scalar(
        select(func.count())
        .select_from(AcquisitionTaskSearchResult)
        .where(AcquisitionTaskSearchResult.acquisition_task_id == created["id"])
    )
    assert linked == 3

    stats = client.get("/liver_api/v1/acquisition-tasks/stats").json()["data"]
    assert stats == {"total": 1, "pending": 0, "running": 0, "completed": 1, "failed": 0}


def test_two_tasks_can_observe_the_same_search_result(client, db_session, fake_generator):
    _set_queries(fake_generator, ["single query"])
    provider = FakeSearchProvider()
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    first = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(
            strategy["id"],
            task_name="首次观察",
            results_per_query=1,
            enterprise_target=1,
        ),
    ).json()["data"]
    second = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(
            strategy["id"],
            task_name="再次观察",
            results_per_query=1,
            enterprise_target=1,
        ),
    ).json()["data"]

    first_run = client.post(f"/liver_api/v1/acquisition-tasks/{first['id']}/run")
    second_run = client.post(f"/liver_api/v1/acquisition-tasks/{second['id']}/run")

    assert first_run.status_code == 200
    assert second_run.status_code == 200
    assert [call["page"] for call in provider.calls] == [1, 2]
    assert db_session.scalar(select(func.count()).select_from(SearchResult)) == 1
    assert (
        db_session.scalar(select(func.count()).select_from(AcquisitionTaskSearchResult)) == 2
    )
    assert len(first_run.json()["data"]["search_results"]) == 1
    assert len(second_run.json()["data"]["search_results"]) == 1
    assert (
        first_run.json()["data"]["search_results"][0]["id"]
        == second_run.json()["data"]["search_results"][0]["id"]
    )


def test_discovery_failure_marks_task_failed(client):
    app.dependency_overrides[get_search_provider] = FailingSearchProvider
    strategy = _create_active_strategy(client)
    created = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    ).json()["data"]

    response = client.post(f"/liver_api/v1/acquisition-tasks/{created['id']}/run")

    assert response.status_code == 200
    task = response.json()["data"]
    assert task["status"] == "failed"
    assert task["failure_reason"] == "provider unavailable"
    assert task["started_at"] is not None
    assert task["finished_at"] is not None


def test_completed_and_running_tasks_cannot_run_again(client, db_session):
    app.dependency_overrides[get_search_provider] = FakeSearchProvider
    strategy = _create_active_strategy(client)
    completed = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    ).json()["data"]
    first_run = client.post(f"/liver_api/v1/acquisition-tasks/{completed['id']}/run")
    assert first_run.status_code == 200

    repeated = client.post(f"/liver_api/v1/acquisition-tasks/{completed['id']}/run")
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "TASK_NOT_RUNNABLE"

    running = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="执行中任务"),
    ).json()["data"]
    row = db_session.get(AcquisitionTask, running["id"])
    row.status = "running"
    db_session.commit()

    conflict = client.post(f"/liver_api/v1/acquisition-tasks/{running['id']}/run")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "TASK_NOT_RUNNABLE"


def test_task_list_detail_and_filters(client):
    strategy = _create_active_strategy(client)
    created = client.post(
        "/liver_api/v1/acquisition-tasks", json=_task_payload(strategy["id"])
    ).json()["data"]

    listed = client.get(
        "/liver_api/v1/acquisition-tasks",
        params={"page": 1, "page_size": 20, "profile_name": strategy["profile_name"]},
    )
    detail = client.get(f"/liver_api/v1/acquisition-tasks/{created['id']}")

    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == created["id"]


def test_query_rotation_prioritizes_never_executed_queries(client):
    provider = FakeSearchProvider()
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)

    for task_name in ("轮转任务 A", "轮转任务 B"):
        task = client.post(
            "/liver_api/v1/acquisition-tasks",
            json=_task_payload(strategy["id"], task_name=task_name, enterprise_target=5),
        ).json()["data"]
        response = client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run")
        assert response.status_code == 200

    assert [call["query"] for call in provider.calls] == [
        "industrial automation manufacturer Germany",
        "Automatisierungstechnik Hersteller",
    ]
    assert [call["page"] for call in provider.calls] == [1, 1]


def test_enterprise_target_counts_only_new_enterprises(client, db_session, fake_generator):
    _set_queries(fake_generator, ["duplicate query", "new query"])
    duplicate_domains = [f"existing-{index}.com" for index in range(5)]
    _seed_enterprises(db_session, duplicate_domains)

    def resolve(query, page, limit):
        domains = duplicate_domains if query == "duplicate query" else ["new.example.net"]
        return [_result(domain, page=page, rank=index + 1) for index, domain in enumerate(domains)]

    provider = RecordingProvider(resolve)
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    task = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(
            strategy["id"],
            task_name="新增企业目标测试",
            max_queries=2,
            results_per_query=5,
            enterprise_target=5,
        ),
    ).json()["data"]

    result = client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run").json()["data"]

    assert result["queries_executed"] == 2
    assert result["valid_domains_count"] == 6
    assert result["new_enterprises_count"] == 1
    assert result["duplicate_enterprises_count"] == 5


def test_two_low_yield_runs_put_query_in_cooldown(client, db_session, fake_generator):
    _set_queries(fake_generator, ["low yield query"])
    domains = [f"low-yield-{index}.com" for index in range(10)]
    _seed_enterprises(db_session, domains[1:])
    provider = RecordingProvider(
        lambda query, page, limit: [
            _result(domain, page=page, rank=index + 1) for index, domain in enumerate(domains)
        ]
    )
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)

    results = []
    for task_name in ("低产出任务 A", "低产出任务 B"):
        task = client.post(
            "/liver_api/v1/acquisition-tasks",
            json=_task_payload(
                strategy["id"],
                task_name=task_name,
                results_per_query=10,
                enterprise_target=50,
            ),
        ).json()["data"]
        results.append(
            client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run").json()["data"]
        )

    query = db_session.scalar(select(StrategyQuery))
    state = db_session.get(StrategyQueryExecutionState, query.id)
    assert results[0]["new_enterprises_count"] == 1
    assert results[1]["new_enterprises_count"] == 0
    assert state.consecutive_low_yield_runs == 2
    assert state.status == "cooldown"
    assert state.cooldown_until is not None


def test_high_yield_run_resets_low_yield_counter(client, db_session, fake_generator):
    _set_queries(fake_generator, ["recovering query"])
    existing = [f"existing-recovery-{index}.com" for index in range(9)]
    _seed_enterprises(db_session, existing)

    def resolve(query, page, limit):
        if page == 1:
            domains = ["first-new.example.com", *existing]
        else:
            domains = [f"recovered-{index}.net" for index in range(5)] + existing[:5]
        return [_result(domain, page=page, rank=index + 1) for index, domain in enumerate(domains)]

    provider = RecordingProvider(resolve)
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    for task_name in ("恢复任务 A", "恢复任务 B"):
        task = client.post(
            "/liver_api/v1/acquisition-tasks",
            json=_task_payload(
                strategy["id"],
                task_name=task_name,
                results_per_query=10,
                enterprise_target=50,
            ),
        ).json()["data"]
        client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run")

    query = db_session.scalar(select(StrategyQuery))
    state = db_session.get(StrategyQueryExecutionState, query.id)
    assert state.consecutive_low_yield_runs == 0
    assert state.status == "active"


def test_cooldown_is_skipped_and_expired_cooldown_reactivates(
    client, db_session, fake_generator
):
    _set_queries(fake_generator, ["cooldown query"])
    provider = RecordingProvider(
        lambda query, page, limit: [_result("cooldown-new.example.com", page=page)]
    )
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    query = db_session.scalar(select(StrategyQuery))
    state = StrategyQueryExecutionState(
        strategy_query_id=query.id,
        next_page=3,
        consecutive_low_yield_runs=2,
        status="cooldown",
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(state)
    db_session.commit()

    skipped = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="冷却跳过任务"),
    ).json()["data"]
    skipped_result = client.post(
        f"/liver_api/v1/acquisition-tasks/{skipped['id']}/run"
    ).json()["data"]
    assert skipped_result["status"] == "completed"
    assert skipped_result["queries_executed"] == 0
    assert provider.calls == []

    state.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    resumed = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="冷却恢复任务"),
    ).json()["data"]
    resumed_result = client.post(
        f"/liver_api/v1/acquisition-tasks/{resumed['id']}/run"
    ).json()["data"]
    db_session.refresh(state)

    assert resumed_result["queries_executed"] == 1
    assert provider.calls[0]["page"] == 3
    assert state.status == "active"
    assert state.consecutive_low_yield_runs == 0


def test_empty_provider_page_marks_query_exhausted(client, db_session, fake_generator):
    _set_queries(fake_generator, ["empty query"])
    provider = RecordingProvider(lambda query, page, limit: [])
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    task = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="空页任务"),
    ).json()["data"]

    result = client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run").json()["data"]
    query = db_session.scalar(select(StrategyQuery))
    state = db_session.get(StrategyQueryExecutionState, query.id)

    assert result["status"] == "completed"
    assert result["query_executions"][0]["provider_returned_count"] == 0
    assert state.status == "exhausted"


def test_query_page_unique_constraint_prevents_double_consumption(
    client, db_session, fake_generator
):
    _set_queries(fake_generator, ["unique page query"])
    provider = RecordingProvider(
        lambda query, page, limit: [_result("unique-page.example.com", page=page)]
    )
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    first = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="唯一页任务 A"),
    ).json()["data"]
    client.post(f"/liver_api/v1/acquisition-tasks/{first['id']}/run")
    second = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="唯一页任务 B"),
    ).json()["data"]
    existing = db_session.scalar(select(AcquisitionTaskQueryExecution))
    db_session.add(
        AcquisitionTaskQueryExecution(
            acquisition_task_id=second["id"],
            strategy_query_id=existing.strategy_query_id,
            page=existing.page,
            requested_limit=5,
            status="running",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_provider_failure_retries_same_page_once(client, db_session, fake_generator):
    _set_queries(fake_generator, ["retry query"])
    provider = RecordingProvider(
        lambda query, page, limit: [_result("retry-success.example.com", page=page)],
        failures=1,
    )
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    task = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="重试成功任务"),
    ).json()["data"]

    result = client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run").json()["data"]
    execution = db_session.scalar(select(AcquisitionTaskQueryExecution))

    assert result["status"] == "completed"
    assert [call["page"] for call in provider.calls] == [1, 1]
    assert execution.status == "completed"
    assert execution.retry_count == 1


def test_second_provider_failure_marks_execution_failed(client, db_session, fake_generator):
    _set_queries(fake_generator, ["failed retry query"])
    provider = RecordingProvider(lambda query, page, limit: [], failures=2)
    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)
    task = client.post(
        "/liver_api/v1/acquisition-tasks",
        json=_task_payload(strategy["id"], task_name="重试失败任务"),
    ).json()["data"]

    result = client.post(f"/liver_api/v1/acquisition-tasks/{task['id']}/run").json()["data"]
    execution = db_session.scalar(select(AcquisitionTaskQueryExecution))

    assert result["status"] == "failed"
    assert [call["page"] for call in provider.calls] == [1, 1]
    assert execution.status == "failed"
    assert execution.retry_count == 1
    assert execution.failure_reason == "temporary provider failure"
    assert execution.finished_at is not None
