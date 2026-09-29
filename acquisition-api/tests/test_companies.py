"""Session B2 candidate enterprise API tests."""

from app.api.deps import get_search_provider
from app.main import app
from tests.test_discovery import FakeSearchProvider, _create_active_strategy


def _seed_discovered_enterprises(client):
    app.dependency_overrides[get_search_provider] = FakeSearchProvider
    strategy = _create_active_strategy(client)
    response = client.post(
        "/liver_api/v1/search-discovery/run",
        json={
            "strategy_id": strategy["id"],
            "max_queries": 1,
            "results_per_query": 3,
            "enterprise_target": 5,
        },
    )
    assert response.status_code == 200
    return strategy


def test_list_companies_returns_real_enterprises_with_pagination(client):
    _seed_discovered_enterprises(client)

    first = client.get(
        "/liver_api/v1/companies", params={"page": 1, "page_size": 1}
    )
    second = client.get(
        "/liver_api/v1/companies", params={"page": 2, "page_size": 1}
    )

    assert first.status_code == 200
    first_page = first.json()["data"]
    second_page = second.json()["data"]
    assert first_page["total"] == 2
    assert first_page["page"] == 1
    assert first_page["page_size"] == 1
    assert len(first_page["list"]) == 1
    assert len(second_page["list"]) == 1
    assert first_page["list"][0]["id"] != second_page["list"][0]["id"]
    assert first_page["list"][0]["country"] == ""
    assert first_page["list"][0]["discovery_summary"]["channels"] == ["google"]
    assert first_page["list"][0]["discovery_sources"] is None


def test_list_companies_filters_by_name_domain_channel_and_pending(client):
    _seed_discovered_enterprises(client)

    by_domain = client.get(
        "/liver_api/v1/companies", params={"company_name": "beta-controls.co.uk"}
    ).json()["data"]
    by_channel = client.get(
        "/liver_api/v1/companies", params={"channel": "google"}
    ).json()["data"]
    pending = client.get(
        "/liver_api/v1/companies", params={"relevance": "pending"}
    ).json()["data"]
    relevant = client.get(
        "/liver_api/v1/companies", params={"relevance": "relevant"}
    ).json()["data"]

    assert by_domain["total"] == 1
    assert by_domain["list"][0]["domain"] == "beta-controls.co.uk"
    assert by_channel["total"] == 2
    assert pending["total"] == 2
    assert relevant["total"] == 0


def test_company_detail_returns_traceable_discovery_sources(client):
    strategy = _seed_discovered_enterprises(client)
    company = client.get("/liver_api/v1/companies").json()["data"]["list"][0]

    response = client.get(f"/liver_api/v1/companies/{company['id']}")

    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["id"] == company["id"]
    assert len(detail["discovery_sources"]) == 1
    source = detail["discovery_sources"][0]
    assert source["strategy_id"] == strategy["id"]
    assert source["strategy_code"] == strategy["code"]
    assert source["query"] == "industrial automation manufacturer Germany"
    assert source["provider"] == "fake-serper"
    assert source["result_url"].startswith("https://")


def test_company_stats_treats_unanalyzed_enterprises_as_pending(client):
    _seed_discovered_enterprises(client)

    response = client.get("/liver_api/v1/companies/stats")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "total": 2,
        "relevant": 0,
        "not_relevant": 0,
        "pending": 2,
    }


def test_missing_company_returns_404(client):
    response = client.get("/liver_api/v1/companies/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
