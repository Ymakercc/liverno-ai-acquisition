"""搜索策略：版本模型、乐观锁、AI 失败隔离。

覆盖冻结规则：
  - 一个 Profile 一套逻辑 SearchStrategy
  - regenerate 只产生新 Draft Version，不动 current_version_id / status
  - 只有显式 Activate 才切换 current_version_id
  - AI 失败不产生任何写入，当前 Active 版本继续生效
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AI_GENERATION_FAILED, AppError
from app.generators.base import GeneratedChannel, GeneratedQuery, GeneratedStrategy
from app.generators.deepseek import parse_generated_strategy
from app.models import SearchStrategy, SearchStrategyVersion, StrategyChannel, StrategyQuery
from tests.conftest import profile_payload


def _create_profile(client, **overrides) -> dict:
    return client.post("/liver_api/v1/profiles", json=profile_payload(**overrides)).json()["data"]


def _generate(client, profile_id: str):
    return client.post("/liver_api/v1/search-strategies/generate", json={"profile_id": profile_id})


def _as_payload(view: dict, *, status: str, version: int, base_version: int) -> dict:
    return {
        "channel_strategies": view["channel_strategies"],
        "status": status,
        "version": version,
        "base_version": base_version,
    }


# ---------------------------------------------------------------- 生成


def test_generate_creates_draft_v1(client, db_session, fake_generator):
    profile = _create_profile(client)
    response = _generate(client, profile["id"])
    assert response.status_code == 200

    view = response.json()["data"]
    assert fake_generator.calls == 1
    assert view["status"] == "draft"
    assert view["version"] == 1
    assert view["base_version"] == 0          # 尚无已提交版本
    assert view["profile_name"] == profile["profile_name"]
    assert view["code"].startswith("STG-")

    assert len(view["channel_strategies"]) == 1
    channel = view["channel_strategies"][0]
    assert channel["channel"] == "google"
    assert channel["target_countries"] == ["DE"]
    assert [q["language"] for q in channel["queries"]] == ["en", "de"]

    # 新建策略 current_version_id 留空，直到显式激活
    strategy = db_session.scalars(select(SearchStrategy)).one()
    assert strategy.current_version_id is None
    assert strategy.status == "draft"

    version = db_session.scalars(select(SearchStrategyVersion)).one()
    assert version.source == "ai_generate"
    assert version.is_committed is False
    assert db_session.scalar(select(func.count()).select_from(StrategyQuery)) == 2


def test_one_logical_strategy_per_profile(client, db_session):
    profile = _create_profile(client)
    first = _generate(client, profile["id"]).json()["data"]
    second = _generate(client, profile["id"]).json()["data"]

    assert second["id"] == first["id"]
    assert second["version"] == 2
    assert db_session.scalar(select(func.count()).select_from(SearchStrategy)) == 1
    assert db_session.scalar(select(func.count()).select_from(SearchStrategyVersion)) == 2

    sources = db_session.scalars(
        select(SearchStrategyVersion.source).order_by(SearchStrategyVersion.version)
    ).all()
    assert list(sources) == ["ai_generate", "ai_regenerate"]


def test_generate_for_missing_profile_returns_404(client, db_session):
    response = _generate(client, "2f6c4d3e-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(SearchStrategy)) == 0


def test_strategy_version_number_is_unique(client, db_session):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]

    db_session.add(
        SearchStrategyVersion(
            strategy_id=view["id"], version=1, source="manual_edit", is_committed=False
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------- 激活


def test_activate_switches_current_version(client, db_session):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]

    saved = client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    ).json()["data"]

    assert saved["status"] == "active"
    assert saved["version"] == 1
    assert saved["base_version"] == 1

    db_session.expire_all()
    strategy = db_session.get(SearchStrategy, view["id"])
    version = db_session.scalars(select(SearchStrategyVersion)).one()
    assert strategy.status == "active"
    assert strategy.current_version_id == version.id
    assert version.is_committed is True

    # 重新读取仍然是激活态的 v1
    reread = client.get(f"/liver_api/v1/search-strategies/{view['id']}").json()["data"]
    assert (reread["status"], reread["version"]) == ("active", 1)
    assert len(reread["channel_strategies"][0]["queries"]) == 2


def test_save_draft_does_not_activate(client, db_session):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]

    saved = client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="draft", version=1, base_version=0),
    ).json()["data"]

    assert saved["status"] == "draft"
    db_session.expire_all()
    strategy = db_session.get(SearchStrategy, view["id"])
    assert strategy.status == "draft"
    assert strategy.current_version_id is None


def test_activate_requires_enabled_channel_with_query(client):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]

    disabled = _as_payload(view, status="active", version=1, base_version=0)
    disabled["channel_strategies"][0]["enabled"] = False

    response = client.put(f"/liver_api/v1/search-strategies/{view['id']}", json=disabled)
    assert response.status_code == 400
    assert response.json()["code"] == "STRATEGY_NOT_ACTIVATABLE"


def test_stale_base_version_conflicts(client):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]
    client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    )

    # 另一个用户仍持有旧的 base_version=0
    response = client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STRATEGY_VERSION_CONFLICT"


def test_pause_and_resume_status(client):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]
    client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    )

    paused = client.patch(
        f"/liver_api/v1/search-strategies/{view['id']}/status", json={"status": "paused"}
    ).json()["data"]
    assert paused["status"] == "paused"

    resumed = client.patch(
        f"/liver_api/v1/search-strategies/{view['id']}/status", json={"status": "active"}
    ).json()["data"]
    assert resumed["status"] == "active"


# ---------------------------------------------------------------- 重新生成不影响 Active


def test_regenerate_does_not_overwrite_active_version(client, db_session, fake_generator):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]
    client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    )

    db_session.expire_all()
    active_version_id = db_session.get(SearchStrategy, view["id"]).current_version_id

    # 换一份内容明显不同的生成结果
    fake_generator.strategy = GeneratedStrategy(
        channels=[
            GeneratedChannel(
                channel="tradeindia",
                enabled=True,
                target_countries=["IN"],
                strategy_summary="改版后的策略",
                queries=[GeneratedQuery(query_text="connector supplier India", country_code="IN")],
            )
        ]
    )
    preview = client.post(
        f"/liver_api/v1/search-strategies/{view['id']}/regenerate"
    ).json()["data"]

    assert preview["version"] == 2                       # 预览新草稿
    assert preview["status"] == "active"                 # 策略本身不被降级
    assert preview["base_version"] == 1                  # 生效版本仍是 v1
    assert preview["channel_strategies"][0]["channel"] == "tradeindia"

    db_session.expire_all()
    strategy = db_session.get(SearchStrategy, view["id"])
    assert strategy.status == "active"
    assert strategy.current_version_id == active_version_id

    new_version = db_session.scalars(
        select(SearchStrategyVersion).where(SearchStrategyVersion.version == 2)
    ).one()
    assert new_version.is_committed is False

    # 默认读取仍返回生效中的 v1 内容
    current = client.get(f"/liver_api/v1/search-strategies/{view['id']}").json()["data"]
    assert current["version"] == 1
    assert current["channel_strategies"][0]["channel"] == "google"


# ---------------------------------------------------------------- AI 失败隔离


def test_ai_failure_writes_nothing(client, db_session, fake_generator):
    profile = _create_profile(client)
    fake_generator.error = AppError("AI 生成失败", status_code=502, code=AI_GENERATION_FAILED)

    response = _generate(client, profile["id"])
    assert response.status_code == 502
    assert response.json()["code"] == AI_GENERATION_FAILED

    assert db_session.scalar(select(func.count()).select_from(SearchStrategy)) == 0
    assert db_session.scalar(select(func.count()).select_from(SearchStrategyVersion)) == 0
    assert db_session.scalar(select(func.count()).select_from(StrategyChannel)) == 0


def test_ai_failure_keeps_active_strategy_intact(client, db_session, fake_generator):
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]
    client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    )
    db_session.expire_all()
    active_version_id = db_session.get(SearchStrategy, view["id"]).current_version_id

    fake_generator.error = RuntimeError("DeepSeek 超时")
    with pytest.raises(RuntimeError):
        client.post(f"/liver_api/v1/search-strategies/{view['id']}/regenerate")

    db_session.rollback()
    strategy = db_session.get(SearchStrategy, view["id"])
    assert strategy.status == "active"
    assert strategy.current_version_id == active_version_id
    assert db_session.scalar(select(func.count()).select_from(SearchStrategyVersion)) == 1

    current = client.get(f"/liver_api/v1/search-strategies/{view['id']}").json()["data"]
    assert current["version"] == 1
    assert len(current["channel_strategies"][0]["queries"]) == 2


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"channels": []}',                                  # 无渠道
        '{"channels": [{"channel": "google", "queries": []}]}',  # 渠道无 Query
        '{"channels": [{"queries": [{"query_text": "x"}]}]}',    # 缺 channel
        '{"channels": [{"channel": "google", "queries": [{"query_text": "  "}]}]}',
    ],
)
def test_invalid_ai_output_is_rejected_before_db(raw):
    with pytest.raises(AppError) as exc:
        parse_generated_strategy(raw)
    assert exc.value.code == AI_GENERATION_FAILED


def test_markdown_fenced_ai_output_is_parsed():
    raw = (
        "```json\n"
        '{"channels": [{"channel": "google", "enabled": true, "target_countries": ["DE"],'
        ' "strategy_summary": "x", "queries": [{"query_text": "connector DE",'
        ' "country_code": "DE", "language": "de"}]}]}\n'
        "```"
    )
    result = parse_generated_strategy(raw)
    assert result.channels[0].queries[0].language == "de"


# ---------------------------------------------------------------- 列表与统计


def test_list_and_stats(client):
    first = _create_profile(client, profile_name="画像甲")
    second = _create_profile(client, profile_name="画像乙")
    view_a = _generate(client, first["id"]).json()["data"]
    _generate(client, second["id"])

    client.put(
        f"/liver_api/v1/search-strategies/{view_a['id']}",
        json=_as_payload(view_a, status="active", version=1, base_version=0),
    )

    page = client.get("/liver_api/v1/search-strategies").json()["data"]
    assert page["total"] == 2

    by_name = client.get(
        "/liver_api/v1/search-strategies", params={"profile_name": "画像甲"}
    ).json()["data"]
    assert by_name["total"] == 1
    assert by_name["list"][0]["profile_name"] == "画像甲"

    by_status = client.get(
        "/liver_api/v1/search-strategies", params={"status": "active"}
    ).json()["data"]
    assert by_status["total"] == 1

    by_channel = client.get(
        "/liver_api/v1/search-strategies", params={"channel": "google"}
    ).json()["data"]
    assert by_channel["total"] == 2

    stats = client.get("/liver_api/v1/search-strategies/stats").json()["data"]
    assert stats == {"total": 2, "active": 1, "draft": 1, "paused": 0}


def test_save_keeps_channel_ai_rejected_with_zero_queries(client, db_session, fake_generator):
    """AI 判定不适用的渠道（0 Query + 说明）必须原样保留，否则前端卡片会凭空消失。"""
    fake_generator.strategy = GeneratedStrategy(
        channels=[
            GeneratedChannel(
                channel="google",
                enabled=True,
                target_countries=["DE"],
                strategy_summary="主渠道",
                queries=[GeneratedQuery(query_text="connector DE", country_code="DE")],
            ),
            GeneratedChannel(
                channel="tradeindia",
                enabled=False,
                target_countries=[],
                strategy_summary="目标市场为西欧，不适用印度 B2B 平台。",
                queries=[],
            ),
        ]
    )
    profile = _create_profile(client)
    view = _generate(client, profile["id"]).json()["data"]
    assert len(view["channel_strategies"]) == 2

    saved = client.put(
        f"/liver_api/v1/search-strategies/{view['id']}",
        json=_as_payload(view, status="active", version=1, base_version=0),
    ).json()["data"]

    assert [c["channel"] for c in saved["channel_strategies"]] == ["google", "tradeindia"]
    rejected = saved["channel_strategies"][1]
    assert rejected["enabled"] is False
    assert rejected["queries"] == []
    assert "不适用" in rejected["strategy_summary"]

    reread = client.get(f"/liver_api/v1/search-strategies/{view['id']}").json()["data"]
    assert len(reread["channel_strategies"]) == 2
