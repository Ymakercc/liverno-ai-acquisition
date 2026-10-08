"""Read-only Marketing Research bridge for one Enterprise."""

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.core.errors import AppError
from app.schemas.research import ResearchOut


def get_research(enterprise_id: str, settings: Settings) -> ResearchOut:
    if not settings.marketing_automation_token:
        raise AppError("背调服务未配置", status_code=503, code="service_unavailable")

    url = (
        f"{settings.marketing_base_url.rstrip('/')}/api/research/by-source/liverno/"
        f"{enterprise_id}"
    )
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {settings.marketing_automation_token}"},
            timeout=settings.marketing_timeout_seconds,
        )
    except httpx.RequestError as exc:
        raise AppError("背调服务暂不可用", status_code=503, code="service_unavailable") from exc

    if response.status_code == 404:
        return ResearchOut(status="not_started")
    if response.status_code in (401, 403):
        raise AppError("背调服务认证失败", status_code=502, code="upstream_auth_error")
    if response.status_code != 200:
        raise AppError("背调服务响应异常", status_code=502, code="upstream_error")

    try:
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("source") != "liverno" or \
                payload.get("source_id") != enterprise_id:
            raise ValueError("unexpected research identity")
        return ResearchOut.model_validate(payload)
    except (ValueError, ValidationError) as exc:
        raise AppError("背调服务数据无效", status_code=502, code="upstream_error") from exc
