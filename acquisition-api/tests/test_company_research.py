"""Read-only company Research bridge; no Marketing calls leave this test process."""

import httpx
import pytest

from app.config import get_settings
from app.main import app
from tests.test_companies import _seed_discovered_enterprises


class ResearchSettings:
    marketing_base_url = "http://marketing.test"
    marketing_automation_token = "test-token"
    marketing_timeout_seconds = 2.0


@pytest.fixture
def company_id(client):
    _seed_discovered_enterprises(client)
    app.dependency_overrides[get_settings] = lambda: ResearchSettings()
    return client.get("/liver_api/v1/companies").json()["data"]["list"][0]["id"]


def mock_response(status, payload=None):
    request = httpx.Request("GET", "http://marketing.test/api/research/by-source/liverno/id")
    return httpx.Response(status, request=request, json=payload) if payload is not None else \
        httpx.Response(status, request=request)


def test_research_requires_existing_enterprise(client, monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("Marketing must not be called")

    monkeypatch.setattr("app.services.research_service.httpx.get", unexpected_call)
    response = client.get("/liver_api/v1/companies/00000000-0000-4000-8000-000000000000/research")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_research_returns_only_approved_fields(client, company_id, monkeypatch):
    def fake_get(url, *, headers, timeout):
        assert url == f"http://marketing.test/api/research/by-source/liverno/{company_id}"
        assert headers == {"Authorization": "Bearer test-token"}
        assert timeout == 2.0
        return mock_response(200, {
            "source": "liverno", "source_id": company_id, "status": "completed",
            "apollo_calls": {"people_match": 2},
            "company": {"apollo_name": "Verified Co", "domain": "verified.example",
                        "match_score": 88, "country": None, "industry": "Automation",
                        "employee_count": 200, "linkedin_url": None,
                        "apollo_organization_id": "apollo-secret", "match_evidence": {}},
            "contacts": [
                {"person_id": "person-1", "name": "Jane", "email": "jane@example.com",
                 "title": "Purchasing", "has_email": True, "email_status": "verified"},
                {"person_id": "person-2", "title": None, "has_email": False,
                 "email_status": None},
            ],
            "website_research": {"status": "fetched", "final_url": "https://verified.example/",
                                 "title": "Verified &amp; Co", "description": "Automation",
                                 "text": "full website text", "keywords": "secret",
                                 "signals": {"meanWellMentioned": True,
                                             "matchedTerms": ["automation"], "directFit": False,
                                             "internal": "hidden"}},
            "qualification": {"status": "review_required", "reason": "Needs review",
                              "customer_profile": "Distributor", "reason_code": "ai_review_required",
                              "recommended_products": [{"name": "PSU", "reason": "Fit"}],
                              "risk_flags": ["uncertain"], "private_prompt": "hidden"},
        })

    monkeypatch.setattr("app.services.research_service.httpx.get", fake_get)
    response = client.get(f"/liver_api/v1/companies/{company_id}/research")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["company"]["apollo_name"] == "Verified Co"
    assert len(data["contacts"]) == 2
    assert data["contacts"][0] == {
        "title": "Purchasing", "has_email": True, "email_status": "verified"
    }
    assert data["website_research"]["status"] == "fetched"
    assert data["website_research"]["title"] == "Verified & Co"
    assert data["qualification"]["status"] == "review_required"
    assert "jane@example.com" not in response.text
    for forbidden in ("person_id", "apollo_organization_id", "match_evidence",
                      "apollo_calls", "full website text", "private_prompt", "internal"):
        assert forbidden not in response.text


def test_research_404_is_not_started(client, company_id, monkeypatch):
    monkeypatch.setattr("app.services.research_service.httpx.get",
                        lambda *args, **kwargs: mock_response(404))
    response = client.get(f"/liver_api/v1/companies/{company_id}/research")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "not_started"


@pytest.mark.parametrize(("status", "code"), [
    (401, "upstream_auth_error"), (403, "upstream_auth_error"),
    (500, "upstream_error"), (503, "upstream_error"),
])
def test_research_upstream_status(client, company_id, monkeypatch, status, code):
    monkeypatch.setattr("app.services.research_service.httpx.get",
                        lambda *args, **kwargs: mock_response(status))
    response = client.get(f"/liver_api/v1/companies/{company_id}/research")
    assert response.status_code == 502
    assert response.json()["code"] == code


def test_research_timeout_is_unavailable(client, company_id, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr("app.services.research_service.httpx.get", timeout)
    response = client.get(f"/liver_api/v1/companies/{company_id}/research")
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"


@pytest.mark.parametrize("payload", ["not json", {"status": "completed"},
                                      {"source": "liverno", "source_id": "wrong",
                                       "status": "completed"}])
def test_research_invalid_response(client, company_id, monkeypatch, payload):
    response = mock_response(200, payload) if isinstance(payload, dict) else \
        httpx.Response(200, text=payload)
    monkeypatch.setattr("app.services.research_service.httpx.get",
                        lambda *args, **kwargs: response)
    result = client.get(f"/liver_api/v1/companies/{company_id}/research")
    assert result.status_code == 502
    assert result.json()["code"] == "upstream_error"
