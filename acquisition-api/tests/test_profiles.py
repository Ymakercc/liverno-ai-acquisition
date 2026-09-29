"""客户画像 CRUD 与约束测试。"""

from sqlalchemy import select

from app.models import CustomerProfile
from tests.conftest import profile_payload


def test_health(client):
    body = client.get("/liver_api/v1/health").json()
    assert body["code"] == 0
    assert "deepseek_configured" in body["data"]


def test_create_profile_persists(client, db_session):
    payload = profile_payload(profile_name="西欧工控OEM")
    response = client.post("/liver_api/v1/profiles", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0

    created = body["data"]
    assert created["profile_name"] == "西欧工控OEM"
    assert created["code"].startswith("PRF-")
    assert created["target_countries"] == ["DE"]
    assert created["daily_quota"] == 60

    # 确认真的落库，而不是只回显提交体
    row = db_session.scalars(
        select(CustomerProfile).where(CustomerProfile.profile_name == "西欧工控OEM")
    ).one()
    assert str(row.id) == created["id"]
    assert row.target_industries == ["industrial_automation"]


def test_get_and_list_profile(client):
    created = client.post("/liver_api/v1/profiles", json=profile_payload()).json()["data"]

    detail = client.get(f"/liver_api/v1/profiles/{created['id']}").json()["data"]
    assert detail["id"] == created["id"]

    page = client.get("/liver_api/v1/profiles", params={"page": 1, "page_size": 20}).json()["data"]
    assert page["total"] == 1
    assert page["list"][0]["id"] == created["id"]


def test_update_profile(client, db_session):
    created = client.post("/liver_api/v1/profiles", json=profile_payload()).json()["data"]

    updated_payload = profile_payload(
        profile_name="改名后的画像",
        daily_quota=120,
        priority="low",
        target_countries=["DE", "FR"],
    )
    updated = client.put(
        f"/liver_api/v1/profiles/{created['id']}", json=updated_payload
    ).json()["data"]
    assert updated["profile_name"] == "改名后的画像"
    assert updated["daily_quota"] == 120
    assert updated["priority"] == "low"
    assert updated["target_countries"] == ["DE", "FR"]

    db_session.expire_all()
    row = db_session.get(CustomerProfile, created["id"])
    assert row.daily_quota == 120


def test_update_profile_status(client):
    created = client.post("/liver_api/v1/profiles", json=profile_payload()).json()["data"]
    assert created["is_enabled"] is True

    result = client.patch(
        f"/liver_api/v1/profiles/{created['id']}/status", json={"is_enabled": False}
    ).json()["data"]
    assert result["is_enabled"] is False


def test_profile_name_must_be_unique(client):
    client.post("/liver_api/v1/profiles", json=profile_payload(profile_name="重名画像"))
    response = client.post("/liver_api/v1/profiles", json=profile_payload(profile_name="重名画像"))

    assert response.status_code == 409
    assert response.json()["code"] == "PROFILE_NAME_DUPLICATED"


def test_daily_quota_out_of_range_rejected(client):
    for quota in (0, 1001):
        response = client.post("/liver_api/v1/profiles", json=profile_payload(daily_quota=quota))
        assert response.status_code == 422, quota


def test_profile_name_too_short_rejected(client):
    response = client.post("/liver_api/v1/profiles", json=profile_payload(profile_name=" A "))
    assert response.status_code == 422


def test_missing_profile_returns_404(client):
    response = client.get("/liver_api/v1/profiles/2f6c4d3e-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_malformed_profile_id_returns_404(client):
    response = client.get("/liver_api/v1/profiles/not-a-uuid")
    assert response.status_code == 404
