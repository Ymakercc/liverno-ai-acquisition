"""Session B1 discovery pipeline tests."""

from sqlalchemy import func, select

from app.api.deps import get_search_provider
from app.generators.base import GeneratedChannel, GeneratedQuery, GeneratedStrategy
from app.models import Enterprise, EnterpriseDiscoverySource, SearchResult, StrategyQuery
from app.providers.base import ProviderSearchResult
from app.services.discovery_service import extract_main_domain
from tests.conftest import profile_payload


class FakeSearchProvider:
    name = "fake-serper"

    def __init__(self):
        self.calls = []

    def search(self, query, *, country_code, language, limit):
        self.calls.append(
            {
                "query": query,
                "country_code": country_code,
                "language": language,
                "limit": limit,
            }
        )
        return [
            ProviderSearchResult(
                title="Acme GmbH - Industrial Automation",
                url="https://www.acme-automation.de/products",
                snippet="Industrial automation manufacturer.",
                rank=1,
                raw={"position": 1},
            ),
            ProviderSearchResult(
                title="Acme GmbH LinkedIn",
                url="https://www.linkedin.com/company/acme",
                snippet="Filtered social domain.",
                rank=2,
                raw={"position": 2},
            ),
            ProviderSearchResult(
                title="Beta Controls Ltd",
                url="https://shop.beta-controls.co.uk/catalog",
                snippet="Control cabinet components.",
                rank=3,
                raw={"position": 3},
            ),
        ][:limit]


def test_extract_main_domain_uses_public_suffix_list():
    cases = {
        "https://www.example.com/products": "example.com",
        "https://shop.example.com/a": "example.com",
        "https://www.example.co.uk/products": "example.co.uk",
        "https://shop.example.com.au/a": "example.com.au",
        "https://abc.example.co.jp/products": "example.co.jp",
    }

    for url, expected in cases.items():
        assert extract_main_domain(url) == expected


def _create_active_strategy(client):
    profile = client.post("/liver_api/v1/profiles", json=profile_payload()).json()["data"]
    view = client.post(
        "/liver_api/v1/search-strategies/generate", json={"profile_id": profile["id"]}
    ).json()["data"]
    payload = {
        "channel_strategies": view["channel_strategies"],
        "status": "active",
        "version": view["version"],
        "base_version": view["base_version"],
    }
    return client.put(f"/liver_api/v1/search-strategies/{view['id']}", json=payload).json()["data"]


def test_run_discovery_persists_results_enterprises_and_sources(client, db_session):
    provider = FakeSearchProvider()
    from app.main import app

    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)

    response = client.post(
        "/liver_api/v1/search-discovery/run",
        json={"strategy_id": strategy["id"], "max_queries": 1, "results_per_query": 3, "enterprise_target": 5},
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["provider"] == "fake-serper"
    assert result["provider_returned_count"] == 3
    assert result["search_result_inserted_count"] == 3
    assert result["valid_domain_count"] == 2
    assert result["enterprise_inserted_count"] == 2
    assert result["enterprise_duplicate_count"] == 0
    assert result["discovery_source_inserted_count"] == 2

    assert provider.calls[0]["limit"] == 3
    assert db_session.scalar(select(func.count()).select_from(SearchResult)) == 3
    assert db_session.scalar(select(func.count()).select_from(Enterprise)) == 2
    assert db_session.scalar(select(func.count()).select_from(EnterpriseDiscoverySource)) == 2

    domains = set(db_session.scalars(select(Enterprise.domain)).all())
    assert domains == {"acme-automation.de", "beta-controls.co.uk"}


def test_run_discovery_deduplicates_enterprise_by_domain(client, db_session):
    provider = FakeSearchProvider()
    from app.main import app

    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)

    payload = {
        "strategy_id": strategy["id"],
        "max_queries": 1,
        "results_per_query": 1,
        "enterprise_target": 1,
    }
    first = client.post("/liver_api/v1/search-discovery/run", json=payload).json()["data"]
    second = client.post("/liver_api/v1/search-discovery/run", json=payload).json()["data"]

    assert first["enterprise_inserted_count"] == 1
    assert second["search_result_existing_count"] == 1
    assert second["enterprise_duplicate_count"] == 1
    assert second["discovery_source_existing_count"] == 1
    assert db_session.scalar(select(func.count()).select_from(Enterprise)) == 1
    assert db_session.scalar(select(func.count()).select_from(SearchResult)) == 1
    assert db_session.scalar(select(func.count()).select_from(EnterpriseDiscoverySource)) == 1


def test_enterprise_country_stays_empty_and_query_country_remains_traceable(
    client, db_session, fake_generator
):
    fake_generator.strategy = GeneratedStrategy(
        channels=[
            GeneratedChannel(
                channel="google",
                enabled=True,
                target_countries=["IT"],
                strategy_summary="Italian PCB search context",
                queries=[
                    GeneratedQuery(
                        query_text="PCB manufacturer Italy terminal connector",
                        country_code="IT",
                        language="en",
                        enabled=True,
                        sort_order=0,
                    )
                ],
            )
        ]
    )
    provider = FakeSearchProvider()
    from app.main import app

    app.dependency_overrides[get_search_provider] = lambda: provider
    strategy = _create_active_strategy(client)

    response = client.post(
        "/liver_api/v1/search-discovery/run",
        json={
            "strategy_id": strategy["id"],
            "max_queries": 1,
            "results_per_query": 1,
            "enterprise_target": 1,
        },
    )

    assert response.status_code == 200
    row = db_session.execute(
        select(
            Enterprise.country.label("enterprise_country"),
            SearchResult.country_code.label("search_context_country"),
            StrategyQuery.country_code.label("strategy_query_country"),
            EnterpriseDiscoverySource.query,
            SearchResult.query_text,
        )
        .select_from(EnterpriseDiscoverySource)
        .join(Enterprise, Enterprise.id == EnterpriseDiscoverySource.enterprise_id)
        .join(SearchResult, SearchResult.id == EnterpriseDiscoverySource.search_result_id)
        .join(StrategyQuery, StrategyQuery.id == SearchResult.query_id)
    ).one()

    assert row.enterprise_country == ""
    assert row.search_context_country == "IT"
    assert row.strategy_query_country == "IT"
    assert row.query == "PCB manufacturer Italy terminal connector"
    assert row.query_text == "PCB manufacturer Italy terminal connector"
