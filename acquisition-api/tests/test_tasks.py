"""Session B3 acquisition task orchestration tests."""

from sqlalchemy import func, select

from app.api.deps import get_search_provider
from app.main import app
from app.models import AcquisitionTask, AcquisitionTaskSearchResult, SearchResult
from tests.test_discovery import FakeSearchProvider, _create_active_strategy


class FailingSearchProvider:
    name = "failing-provider"

    def search(self, query, *, country_code, language, limit):
        raise RuntimeError("provider unavailable")


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


def test_two_tasks_can_observe_the_same_search_result(client, db_session):
    app.dependency_overrides[get_search_provider] = FakeSearchProvider
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
