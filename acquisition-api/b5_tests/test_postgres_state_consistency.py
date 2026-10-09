"""Production-session regression against a disposable PostgreSQL database only."""

import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import create_engine, make_url
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enterprise import Enterprise
from app.models.marketing_handoff import EnterpriseMarketingHandoff
from app.services import company_service, marketing_handoff_service as flow, research_service


def test_disposable_postgres_returns_committed_state(monkeypatch):
    database_url = os.environ.get("B5_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("requires a disposable B5 PostgreSQL container")
    url = make_url(database_url)
    assert os.environ.get("B5_DISPOSABLE_PG") == "1"
    assert url.database == "b5_disposable_test" and (url.host or "").startswith("b5-pg-")
    engine = create_engine(url)
    ids = [uuid.uuid4() for _ in range(4)]
    blocked_id, running_id, queued_id, failed_id = ids
    now = datetime.now(timezone.utc)
    enterprises = {
        blocked_id: SimpleNamespace(id=blocked_id, domain="blocked.example.org",
                                    company_name="Synthetic", country="DE", industry="Automation",
                                    discovery_sources=[]),
    }
    for enterprise_id in ids[1:]:
        enterprises[enterprise_id] = SimpleNamespace(
            id=enterprise_id, domain=f"{str(enterprise_id)[:8]}.example.org",
            company_name="Synthetic", country="DE", industry="Automation",
            discovery_sources=[SimpleNamespace(result_url="https://example.org/", discovered_at=now)],
        )
    with Session(engine, expire_on_commit=False) as db:
        for enterprise in enterprises.values():
            db.add(Enterprise(id=enterprise.id, company_name=enterprise.company_name,
                              normalized_name=str(enterprise.id), domain=enterprise.domain,
                              country="DE", industry="Automation"))
        db.commit()

    def get_company(_db, enterprise_id):
        return enterprises[uuid.UUID(str(enterprise_id))]

    monkeypatch.setattr(company_service, "get_company", get_company)
    settings = SimpleNamespace()
    calls = []

    def current_research(enterprise_id, _settings):
        source_id = uuid.UUID(enterprise_id)
        calls.append(source_id)
        if source_id == running_id:
            with Session(engine, expire_on_commit=False) as observer:
                row = observer.get(EnterpriseMarketingHandoff, running_id)
                assert row.status == "running" and row.run_id is not None
                concurrent = flow.trigger(observer, str(running_id), settings)
                assert concurrent.status == "running"
            return {"id": "research-running", "status": "researching"}
        if source_id == failed_id:
            raise AppError("mock network failure", status_code=503, code="service_unavailable")
        return {
            "id": "research-queued", "status": "completed", "domain": "example.org",
            "company": {"domain": "example.org"},
            "contacts": [{"person_id": "person-1", "has_email": True,
                          "email_status": "verified"}],
            "qualification": {"status": "qualified", "qualified": True},
        }

    monkeypatch.setattr(research_service, "get_record", current_research)
    monkeypatch.setattr(research_service, "get_handoff", lambda *_: {
        "source": "liverno", "sourceId": str(queued_id), "status": "queued",
        "researchId": "research-queued", "qualificationStatus": "qualified",
        "marketingCustomerId": "marketing-queued", "jobId": "job-queued",
        "fumengCustomerId": "",
    })
    monkeypatch.setattr(research_service, "intake_research",
                        lambda *_: pytest.fail("mock C0 already exists"))
    monkeypatch.setattr(research_service, "qualify_research",
                        lambda *_: pytest.fail("mock C1 already exists"))
    monkeypatch.setattr(research_service, "create_handoff",
                        lambda *_: pytest.fail("mock C2 already exists"))

    try:
        with Session(engine, expire_on_commit=False) as db:
            blocked = flow.trigger(db, str(blocked_id), settings)
            assert (blocked.status, blocked.failure_code) == \
                ("blocked", "missing_discovery_evidence")
            assert flow.get_status(db, str(blocked_id)).model_dump() == blocked.model_dump()

            waiting = flow.trigger(db, str(running_id), settings)
            assert (waiting.status, waiting.research_id) == \
                ("waiting_research", "research-running")

            queued = flow.trigger(db, str(queued_id), settings)
            assert (queued.status, queued.research_id, queued.marketing_customer_id, queued.job_id) == \
                ("queued", "research-queued", "marketing-queued", "job-queued")

            failed = flow.trigger(db, str(failed_id), settings)
            assert (failed.status, failed.failure_code) == ("retryable", "service_unavailable")
            assert flow.get_status(db, str(failed_id)).model_dump() == failed.model_dump()

        with Session(engine, expire_on_commit=False) as restarted:
            assert flow.trigger(restarted, str(queued_id), settings).model_dump() == queued.model_dump()
            assert flow.get_status(restarted, str(blocked_id)).model_dump() == blocked.model_dump()
            assert flow.get_status(restarted, str(failed_id)).model_dump() == failed.model_dump()
            assert restarted.get(EnterpriseMarketingHandoff, queued_id).job_id == "job-queued"
        assert calls.count(queued_id) == 1
    finally:
        with Session(engine, expire_on_commit=False) as db:
            db.execute(delete(Enterprise).where(Enterprise.id.in_(ids)))
            db.commit()
        engine.dispose()
