"""B5 tests use only disposable SQLite and mocked Marketing HTTP calls.

This directory is deliberately outside tests/: the legacy conftest drops a
PostgreSQL schema and must never run against the existing business database.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.companies import require_b5_access
from app.config import get_settings
from app.core.errors import AppError
from app.db import Base, get_db
from app.main import app
from app.models.marketing_handoff import EnterpriseMarketingHandoff
from app.services import company_service, marketing_handoff_service as flow, research_service


ID = uuid.UUID("a1111111-1111-4111-8111-a11111111111")
RESEARCH_ID = "research-1"


def settings():
    return SimpleNamespace(marketing_base_url="http://marketing.test",
                           marketing_automation_token="marketing-test-token",
                           marketing_timeout_seconds=2,
                           marketing_step_timeout_seconds=5,
                           b5_trigger_token="operator-test-token")


def record(status="completed", qualification="not_started", qualified=None):
    return {
        "id": RESEARCH_ID, "source": "liverno", "source_id": str(ID),
        "status": status, "domain": "example.org",
        "company": {"domain": "example.org"},
        "contacts": [{"person_id": "person-1", "has_email": True, "email_status": "verified"}],
        "qualification": {"status": qualification, "qualified": qualified},
    }


def handoff(status="queued"):
    return {
        "source": "liverno", "sourceId": str(ID), "status": status,
        "researchId": RESEARCH_ID, "qualificationStatus": "qualified",
        "marketingCustomerId": "marketing-1", "jobId": "job-1" if status == "queued" else None,
        "fumengCustomerId": "", "failureReason": "",
    }


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'b5.sqlite'}")
    Base.metadata.create_all(engine, tables=[EnterpriseMarketingHandoff.__table__])
    enterprise = SimpleNamespace(
        id=ID, domain="example.org", company_name="Synthetic Co",
        country="DE", industry="Automation",
        discovery_sources=[SimpleNamespace(result_url="https://example.org/",
                                           discovered_at=datetime.now(timezone.utc))],
    )
    monkeypatch.setattr(company_service, "get_company", lambda _db, _id: enterprise)
    yield engine, enterprise
    engine.dispose()


def test_full_flow_reuses_marketing_ids_and_survives_new_session(fixture, monkeypatch):
    engine, _ = fixture
    calls = []
    monkeypatch.setattr(research_service, "get_record", lambda *_: calls.append("get_c0") or None)
    monkeypatch.setattr(research_service, "intake_research",
                        lambda *_: calls.append("c0") or record())
    monkeypatch.setattr(research_service, "qualify_research",
                        lambda *_: calls.append("c1") or record(qualification="qualified", qualified=True))
    monkeypatch.setattr(research_service, "get_handoff", lambda *_: calls.append("get_c2") or None)
    monkeypatch.setattr(research_service, "create_handoff", lambda *_: calls.append("c2") or handoff())
    with Session(engine, expire_on_commit=False) as db:
        result = flow.trigger(db, str(ID), settings())
        assert (result.status, result.research_id, result.marketing_customer_id, result.job_id) == \
            ("queued", RESEARCH_ID, "marketing-1", "job-1")
        persisted = flow.get_status(db, str(ID))
        assert persisted.model_dump(exclude={"updated_at"}) == result.model_dump(exclude={"updated_at"})
        row = db.get(EnterpriseMarketingHandoff, ID, populate_existing=True)
        assert (row.status, row.research_id, row.marketing_customer_id, row.job_id) == \
            ("queued", RESEARCH_ID, "marketing-1", "job-1")
    assert calls == ["get_c0", "c0", "c1", "get_c2", "c2"]
    with Session(engine, expire_on_commit=False) as restarted_db:
        assert flow.trigger(restarted_db, str(ID), settings()).job_id == "job-1"
        assert flow.get_status(restarted_db, str(ID)).attempt_count == 1
    assert calls == ["get_c0", "c0", "c1", "get_c2", "c2"]


def test_incomplete_c0_waits_without_c1_or_c2(fixture, monkeypatch):
    engine, _ = fixture
    monkeypatch.setattr(research_service, "get_record", lambda *_: record(status="researching"))
    monkeypatch.setattr(research_service, "qualify_research",
                        lambda *_: pytest.fail("C1 must wait for C0"))
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("C2 must wait for C0"))
    with Session(engine, expire_on_commit=False) as db:
        result = flow.trigger(db, str(ID), settings())
        assert (result.status, result.stage, result.research_id) == \
            ("waiting_research", "research", RESEARCH_ID)


def test_pending_is_persisted_as_running_before_marketing_call(fixture, monkeypatch):
    engine, _ = fixture

    def during_c0(*_):
        with Session(engine, expire_on_commit=False) as observer:
            row = observer.get(EnterpriseMarketingHandoff, ID)
            assert row.status == "running"
            assert row.stage == "research"
            assert row.run_id is not None
            assert row.lease_until is not None
        return record(status="researching")

    monkeypatch.setattr(research_service, "get_record", during_c0)
    with Session(engine, expire_on_commit=False) as db:
        result = flow.trigger(db, str(ID), settings())
        assert result.status == "waiting_research"
        assert flow.get_status(db, str(ID)).status == result.status


def test_qualification_in_progress_waits_without_repeating_paid_work(fixture, monkeypatch):
    engine, _ = fixture
    monkeypatch.setattr(research_service, "get_record",
                        lambda *_: record(qualification="qualifying"))
    monkeypatch.setattr(research_service, "qualify_research",
                        lambda *_: pytest.fail("C1 is already in progress"))
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("C2 must wait for C1"))
    with Session(engine, expire_on_commit=False) as db:
        assert flow.trigger(db, str(ID), settings()).status == "waiting_qualification"


@pytest.mark.parametrize("decision", ["review_required", "not_qualified", "failed"])
def test_nonqualified_c1_blocks_handoff(fixture, monkeypatch, decision):
    engine, _ = fixture
    monkeypatch.setattr(research_service, "get_record",
                        lambda *_: record(qualification=decision, qualified=False))
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("C2 must not run"))
    with Session(engine, expire_on_commit=False) as db:
        result = flow.trigger(db, str(ID), settings())
        assert (result.status, result.stage, result.failure_code) == ("blocked", "qualification", decision)


def test_missing_contact_and_domain_mismatch_block_before_c2(fixture, monkeypatch):
    engine, _ = fixture
    current = record(qualification="qualified", qualified=True)
    current["contacts"] = []
    monkeypatch.setattr(research_service, "get_record", lambda *_: current)
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("C2 must not run"))
    with Session(engine, expire_on_commit=False) as db:
        assert flow.trigger(db, str(ID), settings()).failure_code == "missing_verified_contact"
        current["contacts"] = record()["contacts"]
        current["company"]["domain"] = "different.example"
        assert flow.trigger(db, str(ID), settings(), retry_blocked=True).failure_code == "identity_domain_mismatch"


def test_network_failure_persists_and_retry_reads_existing_marketing_state(fixture, monkeypatch):
    engine, _ = fixture
    calls = []

    def unavailable(*_):
        calls.append("get_c0")
        raise AppError("unavailable", status_code=503, code="service_unavailable")

    monkeypatch.setattr(research_service, "get_record", unavailable)
    with Session(engine, expire_on_commit=False) as db:
        first = flow.trigger(db, str(ID), settings())
        assert (first.status, first.failure_code) == ("retryable", "service_unavailable")
        assert (flow.get_status(db, str(ID)).status, flow.get_status(db, str(ID)).failure_code) == \
            (first.status, first.failure_code)
    monkeypatch.setattr(research_service, "get_record",
                        lambda *_: calls.append("get_c0") or record(qualification="qualified", qualified=True))
    monkeypatch.setattr(research_service, "intake_research",
                        lambda *_: pytest.fail("C0 already exists"))
    monkeypatch.setattr(research_service, "qualify_research",
                        lambda *_: pytest.fail("C1 already exists"))
    monkeypatch.setattr(research_service, "get_handoff",
                        lambda *_: calls.append("get_c2") or handoff())
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("C2 already exists"))
    with Session(engine, expire_on_commit=False) as restarted_db:
        resumed = flow.trigger(restarted_db, str(ID), settings())
        assert (resumed.status, resumed.attempt_count, resumed.job_id) == ("queued", 2, "job-1")
    assert calls == ["get_c0", "get_c0", "get_c2"]


def test_failed_c2_needs_explicit_retry_before_any_paid_preparation(fixture, monkeypatch):
    engine, _ = fixture
    calls = []
    monkeypatch.setattr(research_service, "get_record",
                        lambda *_: record(qualification="qualified", qualified=True))
    failed = {**handoff("failed"), "failureReason": "draft_quality_failed"}
    monkeypatch.setattr(research_service, "get_handoff",
                        lambda *_: calls.append("get_c2") or failed)
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: calls.append("c2") or handoff())
    with Session(engine, expire_on_commit=False) as db:
        first = flow.trigger(db, str(ID), settings())
        assert (first.status, first.failure_code) == ("blocked", "draft_quality_failed")
        assert flow.trigger(db, str(ID), settings()).status == "blocked"
        assert calls == ["get_c2"]
        assert flow.trigger(db, str(ID), settings(), retry_blocked=True).status == "queued"
        assert calls == ["get_c2", "get_c2", "c2"]


def test_preparing_c2_is_queried_without_duplicate_post(fixture, monkeypatch):
    engine, _ = fixture
    monkeypatch.setattr(research_service, "get_record",
                        lambda *_: record(qualification="qualified", qualified=True))
    monkeypatch.setattr(research_service, "get_handoff", lambda *_: handoff("preparing"))
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("preparing C2 must not be repeated"))
    with Session(engine, expire_on_commit=False) as db:
        assert flow.trigger(db, str(ID), settings()).status == "waiting_handoff"


def test_active_lease_prevents_duplicate_run_and_expired_lease_recovers(fixture, monkeypatch):
    engine, _ = fixture
    with Session(engine, expire_on_commit=False) as db:
        db.add(EnterpriseMarketingHandoff(
            enterprise_id=ID, status="running", stage="research", attempt_count=1,
            run_id=uuid.uuid4(), lease_until=datetime.now(timezone.utc) + timedelta(minutes=2),
        ))
        db.commit()
        monkeypatch.setattr(research_service, "get_record",
                            lambda *_: pytest.fail("active run must not make a request"))
        assert flow.trigger(db, str(ID), settings()).status == "running"
        row = db.get(EnterpriseMarketingHandoff, ID)
        row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(research_service, "get_record", lambda *_: record(status="researching"))
    with Session(engine, expire_on_commit=False) as restarted_db:
        result = flow.trigger(restarted_db, str(ID), settings())
        assert (result.status, result.attempt_count) == ("waiting_research", 2)


def test_backend_trigger_requires_own_token(fixture):
    engine, _ = fixture

    def db_override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_settings] = settings
    try:
        with TestClient(app) as client:
            path = f"/liver_api/v1/companies/{ID}/marketing-handoff"
            assert client.get(path).status_code == 401
            assert client.post(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
            response = client.get(path, headers={"Authorization": "Bearer operator-test-token"})
            assert response.status_code == 200
            assert response.json()["data"]["status"] == "not_started"
    finally:
        app.dependency_overrides.clear()


def test_missing_evidence_api_response_matches_persisted_blocked_state(fixture):
    engine, enterprise = fixture
    enterprise.discovery_sources.clear()

    def db_override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_settings] = settings
    try:
        with TestClient(app) as client:
            path = f"/liver_api/v1/companies/{ID}/marketing-handoff"
            headers = {"Authorization": "Bearer operator-test-token"}
            first = client.post(path, headers=headers)
            assert first.status_code == 200
            data = first.json()["data"]
            assert (data["status"], data["failure_code"]) == \
                ("blocked", "missing_discovery_evidence")
            assert client.get(path, headers=headers).json()["data"] == data
            assert client.post(path, headers=headers).json()["data"] == data
        with Session(engine, expire_on_commit=False) as db:
            row = db.get(EnterpriseMarketingHandoff, ID)
            assert (row.status, row.failure_code, row.attempt_count) == \
                ("blocked", "missing_discovery_evidence", 1)
    finally:
        app.dependency_overrides.clear()


def test_409_blocked_response_is_fresh(fixture, monkeypatch):
    engine, _ = fixture

    def conflict(*_):
        raise AppError("blocked", status_code=409, code="QUALIFICATION_REQUIRED")

    monkeypatch.setattr(research_service, "get_record", conflict)
    with Session(engine, expire_on_commit=False) as db:
        result = flow.trigger(db, str(ID), settings())
        assert (result.status, result.failure_code) == ("blocked", "QUALIFICATION_REQUIRED")
        assert flow.get_status(db, str(ID)).failure_code == result.failure_code


@pytest.mark.parametrize("status,expected", [
    (401, "upstream_auth_error"), (403, "upstream_auth_error"),
    (409, "QUALIFICATION_REQUIRED"), (500, "upstream_error"),
])
def test_marketing_client_maps_status_without_exposing_response(monkeypatch, status, expected):
    response = httpx.Response(status, request=httpx.Request("POST", "http://marketing.test"),
                              json={"error": {"code": "QUALIFICATION_REQUIRED"}})
    monkeypatch.setattr(research_service.httpx, "post", lambda *_args, **_kwargs: response)
    with pytest.raises(AppError) as error:
        research_service.create_handoff(str(ID), settings())
    assert error.value.code == expected


def test_marketing_client_timeout_is_retryable(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise httpx.ReadTimeout("mock timeout")
    monkeypatch.setattr(research_service.httpx, "get", timeout)
    with pytest.raises(AppError) as error:
        research_service.get_record(str(ID), settings())
    assert error.value.code == "service_unavailable"


def test_marketing_client_uses_backend_bearer_and_existing_c0_c1_c2_routes(monkeypatch):
    requests = []
    research = {
        **record(), "website_research": {"status": "not_started", "signals": {}},
    }

    def fake_get(url, *, headers, timeout):
        requests.append(("GET", url, headers, timeout))
        payload = handoff() if url.endswith("/handoff") else research
        return httpx.Response(200, request=httpx.Request("GET", url), json=payload)

    def fake_post(url, *, headers, timeout, json=None):
        requests.append(("POST", url, headers, timeout, json))
        payload = handoff() if url.endswith("/handoff") else research
        return httpx.Response(200, request=httpx.Request("POST", url), json=payload)

    monkeypatch.setattr(research_service.httpx, "get", fake_get)
    monkeypatch.setattr(research_service.httpx, "post", fake_post)
    assert research_service.get_record(str(ID), settings())["id"] == RESEARCH_ID
    body = {"source": "liverno", "source_id": str(ID)}
    assert research_service.intake_research(str(ID), body, settings())["id"] == RESEARCH_ID
    assert research_service.qualify_research(RESEARCH_ID, str(ID), settings())["id"] == RESEARCH_ID
    assert research_service.get_handoff(str(ID), settings())["jobId"] == "job-1"
    assert research_service.create_handoff(str(ID), settings())["jobId"] == "job-1"
    assert [item[0] for item in requests] == ["GET", "POST", "POST", "GET", "POST"]
    assert requests[1][-1] == body
    assert all(item[2] == {"Authorization": "Bearer marketing-test-token"} for item in requests)
    assert all(item[1].startswith("http://marketing.test/api/research/") for item in requests)
