"""Serper Google Search provider."""

import httpx

from app.config import get_settings
from app.core.errors import ValidationError
from app.providers.base import ProviderSearchResult


class SerperSearchProvider:
    name = "serper"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.serper_api_key:
            raise ValidationError("SERPER_API_KEY 未配置", code="SERPER_NOT_CONFIGURED")
        self.api_key = settings.serper_api_key
        self.base_url = settings.serper_base_url.rstrip("/")
        self.timeout = settings.serper_timeout_seconds

    def search(
        self,
        query: str,
        *,
        country_code: str | None,
        language: str | None,
        limit: int,
        page: int,
    ) -> list[ProviderSearchResult]:
        payload: dict[str, object] = {"q": query, "num": limit, "page": page}
        if country_code:
            payload["gl"] = country_code.lower()
        if language:
            payload["hl"] = language.lower()

        try:
            response = httpx.post(
                f"{self.base_url}/search",
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValidationError(f"Serper 搜索失败：{exc}", code="SERPER_SEARCH_FAILED") from exc

        body = response.json()
        organic = body.get("organic") or []
        results: list[ProviderSearchResult] = []
        for index, item in enumerate(organic[:limit]):
            url = str(item.get("link") or "").strip()
            if not url:
                continue
            results.append(
                ProviderSearchResult(
                    title=str(item.get("title") or "").strip(),
                    url=url,
                    snippet=str(item.get("snippet") or "").strip(),
                    rank=int(item.get("position") or index + 1),
                    raw=item,
                )
            )
        return results
