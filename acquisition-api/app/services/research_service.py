"""Backend-only Marketing API client for one Liverno Enterprise."""

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.core.errors import AppError
from app.schemas.research import ResearchOut


def _request(method: str, path: str, settings: Settings, *, payload: dict | None = None,
             long_running: bool = False) -> dict | None:
    if not settings.marketing_automation_token:
        raise AppError("背调服务未配置", status_code=503, code="service_unavailable")
    url = f"{settings.marketing_base_url.rstrip('/')}{path}"
    options = {
        "headers": {"Authorization": f"Bearer {settings.marketing_automation_token}"},
        "timeout": min(max(settings.marketing_step_timeout_seconds, 1), 240)
        if long_running else min(max(settings.marketing_timeout_seconds, 1), 30),
    }
    try:
        if method == "GET":
            response = httpx.get(url, **options)
        elif payload is None:
            response = httpx.post(url, **options)
        else:
            response = httpx.post(url, json=payload, **options)
    except httpx.RequestError as exc:
        raise AppError("营销服务暂不可用", status_code=503, code="service_unavailable") from exc

    if response.status_code == 404:
        return None
    if response.status_code in (401, 403):
        raise AppError("营销服务认证失败", status_code=502, code="upstream_auth_error")
    if response.status_code == 409:
        try:
            code = response.json().get("error", {}).get("code", "upstream_conflict")
        except ValueError:
            code = "upstream_conflict"
        if not isinstance(code, str) or not code.isidentifier() or len(code) > 80:
            code = "upstream_conflict"
        raise AppError("营销服务拒绝当前状态", status_code=409, code=code)
    if response.status_code == 503:
        if long_running:
            raise AppError("营销服务暂不可用", status_code=503, code="service_unavailable")
        raise AppError("营销服务响应异常", status_code=502, code="upstream_error")
    if response.status_code not in (200, 201):
        raise AppError("营销服务响应异常", status_code=502, code="upstream_error")
    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("response must be an object")
        return result
    except ValueError as exc:
        raise AppError("营销服务数据无效", status_code=502, code="upstream_error") from exc


def _research_record(payload: dict | None, enterprise_id: str) -> dict | None:
    if payload is None:
        return None
    try:
        if payload.get("source") != "liverno" or payload.get("source_id") != enterprise_id or \
                not isinstance(payload.get("id"), str) or not payload["id"]:
            raise ValueError("unexpected research identity")
        ResearchOut.model_validate(payload)
        return payload
    except (ValueError, ValidationError) as exc:
        raise AppError("营销服务数据无效", status_code=502, code="upstream_error") from exc


def get_record(enterprise_id: str, settings: Settings) -> dict | None:
    return _research_record(_request(
        "GET", f"/api/research/by-source/liverno/{enterprise_id}", settings
    ), enterprise_id)


def intake_research(enterprise_id: str, body: dict, settings: Settings) -> dict:
    result = _research_record(_request(
        "POST", "/api/research/intake", settings, payload=body, long_running=True
    ), enterprise_id)
    if result is None:
        raise AppError("营销服务数据无效", status_code=502, code="upstream_error")
    return result


def qualify_research(research_id: str, enterprise_id: str, settings: Settings) -> dict:
    result = _research_record(_request(
        "POST", f"/api/research/{research_id}/qualify", settings, long_running=True
    ), enterprise_id)
    if result is None or result["id"] != research_id:
        raise AppError("营销服务数据无效", status_code=502, code="upstream_error")
    return result


def get_handoff(enterprise_id: str, settings: Settings) -> dict | None:
    return _handoff(_request(
        "GET", f"/api/research/by-source/liverno/{enterprise_id}/handoff", settings
    ), enterprise_id)


def create_handoff(enterprise_id: str, settings: Settings) -> dict:
    result = _handoff(_request(
        "POST", f"/api/research/by-source/liverno/{enterprise_id}/handoff",
        settings, long_running=True
    ), enterprise_id)
    if result is None:
        raise AppError("营销服务数据无效", status_code=502, code="upstream_error")
    return result


def _handoff(payload: dict | None, enterprise_id: str) -> dict | None:
    if payload is None:
        return None
    if payload.get("source") != "liverno" or payload.get("sourceId") != enterprise_id or \
            not isinstance(payload.get("status"), str):
        raise AppError("营销交接身份无效", status_code=502, code="upstream_error")
    return payload


def get_research(enterprise_id: str, settings: Settings) -> ResearchOut:
    payload = _request("GET", f"/api/research/by-source/liverno/{enterprise_id}", settings)
    if payload is None:
        return ResearchOut(status="not_started")
    try:
        if not isinstance(payload, dict) or payload.get("source") != "liverno" or \
                payload.get("source_id") != enterprise_id:
            raise ValueError("unexpected research identity")
        return ResearchOut.model_validate(payload)
    except (ValueError, ValidationError) as exc:
        raise AppError("背调服务数据无效", status_code=502, code="upstream_error") from exc
