"""DeepSeek 策略生成器。

Key 只从配置读取，禁止打印 / 入库 / 返回前端。
"""

import json
import logging

import httpx
from pydantic import ValidationError as PydanticValidationError

from app.config import Settings, get_settings
from app.core.errors import AI_GENERATION_FAILED, AppError
from app.generators.base import GeneratedStrategy, StrategyGenerator
from app.models import CustomerProfile

logger = logging.getLogger(__name__)

# P0 渠道，与前端字典保持一致；渠道可扩展，不在业务代码写死判断
SUPPORTED_CHANNELS = ["google", "company_site", "tradeindia", "b2b"]

SYSTEM_PROMPT = """You are a B2B lead-generation search strategist for KULON ELECTRONICS,
a supplier of industrial connectors, wire harnesses and power components.

Your job: turn a customer profile into concrete, executable web search queries that will
find REAL target companies on each channel.

Rules:
- Output ONLY valid JSON. No markdown fence, no commentary.
- Decide the search language per query yourself, based on channel, country and intent.
  Do NOT mechanically map one country to one language. The same country may need both
  an English query and a local-language query when that improves recall.
- language must be an ISO 639-1 code (en, de, it, fr, es, nl, pl, tr, pt, ja, ko, vi) or null.
- country_code must be ISO 3166-1 alpha-2 or null.
- Queries must be directly usable in a search engine or B2B site search.
- Use the profile's exclude_signals to add negative keywords where the channel supports it.
- Use required_signals to bias queries toward companies that show those signals.
- Disable a channel (enabled=false) when the profile clearly does not fit it,
  for example tradeindia when India is not among the target countries.

JSON schema:
{
  "channels": [
    {
      "channel": "google | company_site | tradeindia | b2b",
      "enabled": true,
      "target_countries": ["DE"],
      "strategy_summary": "one short sentence in Chinese explaining this channel's approach",
      "queries": [
        {
          "query_text": "...",
          "country_code": "DE",
          "language": "de",
          "enabled": true,
          "sort_order": 0
        }
      ]
    }
  ]
}"""


def _build_user_prompt(profile: CustomerProfile) -> str:
    """只喂业务语义字段；daily_quota 不参与搜索内容生成。"""
    payload = {
        "profile_name": profile.profile_name,
        "target_industries": profile.target_industries,
        "target_regions": profile.target_regions,
        "target_countries": profile.target_countries,
        "company_types": profile.company_types,
        "company_size": profile.company_size,
        "product_lines": profile.product_lines,
        "application_scenarios": profile.application_scenarios,
        "required_signals": profile.required_signals,
        "exclude_signals": profile.exclude_signals,
        "target_roles": profile.target_roles,
    }
    return (
        "Customer profile:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + f"\n\nGenerate search strategies for these channels: {', '.join(SUPPORTED_CHANNELS)}."
        + "\nReturn JSON only."
    )


class DeepSeekStrategyGenerator(StrategyGenerator):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def generate(self, profile: CustomerProfile) -> GeneratedStrategy:
        if not self.settings.deepseek_configured:
            raise AppError(
                "DeepSeek 未配置，无法生成搜索策略",
                status_code=503,
                code=AI_GENERATION_FAILED,
            )

        body = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(profile)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }

        try:
            with httpx.Client(timeout=self.settings.deepseek_timeout_seconds) as client:
                response = client.post(
                    f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.HTTPError as exc:
            # 只记录异常类型，不记录请求头，避免 Key 进日志
            logger.warning("DeepSeek request failed: %s", type(exc).__name__)
            raise AppError(
                "调用 DeepSeek 失败，请稍后重试", status_code=502, code=AI_GENERATION_FAILED
            ) from exc

        if response.status_code >= 400:
            logger.warning("DeepSeek returned HTTP %s", response.status_code)
            raise AppError(
                f"DeepSeek 返回异常状态 {response.status_code}",
                status_code=502,
                code=AI_GENERATION_FAILED,
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise AppError(
                "DeepSeek 返回结构无法解析", status_code=502, code=AI_GENERATION_FAILED
            ) from exc

        return parse_generated_strategy(content)


def parse_generated_strategy(content: str) -> GeneratedStrategy:
    """把模型输出解析并校验为 GeneratedStrategy。

    无效 JSON / 空 Query / 字段错误一律抛异常，绝不写入半成品数据。
    """
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError(
            "DeepSeek 返回的不是合法 JSON", status_code=502, code=AI_GENERATION_FAILED
        ) from exc

    try:
        return GeneratedStrategy.model_validate(raw)
    except PydanticValidationError as exc:
        raise AppError(
            f"DeepSeek 返回的策略结构不合法：{exc.error_count()} 处字段错误",
            status_code=502,
            code=AI_GENERATION_FAILED,
        ) from exc
