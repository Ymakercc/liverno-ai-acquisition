"""搜索策略业务逻辑。

冻结规则（以此为准，前端 Mock 不一致的部分不作为依据）：
  1. 一个 Profile 一套逻辑 SearchStrategy
  2. regenerate 创建新 Draft Version，写入 Channel / Query
     —— 不修改 current_version_id，不降低 search_strategy.status
  3. 保存草稿只影响新 Version
  4. 只有显式 Activate 才切换 current_version_id 并置 status=active（同一事务）
  5. 全新 Strategy 可以是 draft，current_version_id 可为空
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import (
    STRATEGY_NOT_ACTIVATABLE,
    STRATEGY_VERSION_CONFLICT,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.generators.base import GeneratedStrategy, StrategyGenerator
from app.models import (
    CustomerProfile,
    SearchStrategy,
    SearchStrategyVersion,
    StrategyChannel,
    StrategyQuery,
)
from app.schemas.strategy import ChannelSearchStrategyIn
from app.services.code_gen import next_code
from app.services.profile_service import get_profile

ACTIVATE_HINT = "至少启用一个搜索渠道，并保留一条有效搜索 Query。"


def _to_uuid(value: str, message: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotFoundError(message) from exc


def can_activate(channels: list[ChannelSearchStrategyIn]) -> bool:
    """draft -> active 的完整校验，与前端 canActivate 同口径。"""
    return any(
        channel.enabled
        and any(q.enabled and q.query_text.strip() for q in channel.queries)
        for channel in channels
    )


# ---------------------------------------------------------------- 读取


def _load_strategy(db: Session, strategy_id: str) -> SearchStrategy:
    strategy = db.get(SearchStrategy, _to_uuid(strategy_id, "搜索策略不存在"))
    if strategy is None:
        raise NotFoundError("搜索策略不存在")
    return strategy


def _latest_version(db: Session, strategy: SearchStrategy) -> SearchStrategyVersion | None:
    """展示用版本：优先当前生效版本，否则取最新一个版本。"""
    if strategy.current_version_id:
        return db.get(SearchStrategyVersion, strategy.current_version_id)
    stmt = (
        select(SearchStrategyVersion)
        .where(SearchStrategyVersion.strategy_id == strategy.id)
        .order_by(SearchStrategyVersion.version.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _committed_version_number(db: Session, strategy: SearchStrategy) -> int:
    """乐观锁基准：当前生效版本号；尚未激活时取最大已提交版本，都没有则 0。"""
    if strategy.current_version_id:
        current = db.get(SearchStrategyVersion, strategy.current_version_id)
        if current:
            return current.version
    stmt = (
        select(func.max(SearchStrategyVersion.version))
        .where(SearchStrategyVersion.strategy_id == strategy.id)
        .where(SearchStrategyVersion.is_committed.is_(True))
    )
    return int(db.scalar(stmt) or 0)


def _max_version_number(db: Session, strategy_id: uuid.UUID) -> int:
    stmt = select(func.max(SearchStrategyVersion.version)).where(
        SearchStrategyVersion.strategy_id == strategy_id
    )
    return int(db.scalar(stmt) or 0)


def _load_version_channels(db: Session, version_id: uuid.UUID) -> list[StrategyChannel]:
    stmt = (
        select(StrategyChannel)
        .where(StrategyChannel.version_id == version_id)
        .options(selectinload(StrategyChannel.queries))
        .order_by(StrategyChannel.sort_order)
    )
    return list(db.scalars(stmt).all())


def build_strategy_view(
    db: Session,
    strategy: SearchStrategy,
    *,
    version: SearchStrategyVersion | None = None,
) -> dict:
    """组装成前端 SearchStrategy 契约结构。"""
    profile = db.get(CustomerProfile, strategy.profile_id)
    target_version = version or _latest_version(db, strategy)

    channels_payload = []
    if target_version is not None:
        for channel in _load_version_channels(db, target_version.id):
            channels_payload.append(
                {
                    "channel": channel.channel,
                    "enabled": channel.enabled,
                    "target_countries": list(channel.target_countries or []),
                    "strategy_summary": channel.strategy_summary or None,
                    "queries": [
                        {
                            "id": str(q.id),
                            "query_text": q.query_text,
                            "country_code": q.country_code,
                            "language": q.language,
                            "enabled": q.enabled,
                        }
                        for q in channel.queries
                    ],
                }
            )

    return {
        "id": str(strategy.id),
        "code": strategy.code,
        "profile_id": str(strategy.profile_id),
        "profile_name": profile.profile_name if profile else "",
        "profile_enabled": profile.is_enabled if profile else None,
        "status": strategy.status,
        "version": target_version.version if target_version else 0,
        "base_version": _committed_version_number(db, strategy),
        "channel_strategies": channels_payload,
        "created_at": strategy.created_at,
        "updated_at": strategy.updated_at,
    }


def list_strategies(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    profile_name: str | None = None,
    profile_id: str | None = None,
    channel: str | None = None,
    status: str | None = None,
) -> tuple[list[dict], int]:
    stmt = select(SearchStrategy).join(
        CustomerProfile, CustomerProfile.id == SearchStrategy.profile_id
    )
    count_stmt = select(func.count()).select_from(SearchStrategy).join(
        CustomerProfile, CustomerProfile.id == SearchStrategy.profile_id
    )

    conditions = []
    if profile_name:
        conditions.append(CustomerProfile.profile_name.ilike(f"%{profile_name.strip()}%"))
    if profile_id:
        conditions.append(SearchStrategy.profile_id == _to_uuid(profile_id, "画像不存在"))
    if status:
        conditions.append(SearchStrategy.status == status)

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    rows = list(db.scalars(stmt.order_by(SearchStrategy.updated_at.desc())).all())
    views = [build_strategy_view(db, item) for item in rows]

    # 渠道筛选作用于当前展示版本，放在组装后过滤
    if channel:
        views = [
            v for v in views
            if any(c["channel"] == channel for c in v["channel_strategies"])
        ]
        total = len(views)
    else:
        total = db.scalar(count_stmt) or 0

    start = (page - 1) * page_size
    return views[start : start + page_size], total


def get_strategy_stats(db: Session) -> dict:
    stmt = select(SearchStrategy.status, func.count()).group_by(SearchStrategy.status)
    counts = {status: int(count) for status, count in db.execute(stmt).all()}
    return {
        "total": sum(counts.values()),
        "active": counts.get("active", 0),
        "draft": counts.get("draft", 0),
        "paused": counts.get("paused", 0),
    }


def get_strategy_view(db: Session, strategy_id: str) -> dict:
    return build_strategy_view(db, _load_strategy(db, strategy_id))


# ---------------------------------------------------------------- 写入


def _write_version_content(
    db: Session,
    version: SearchStrategyVersion,
    channels: list,
) -> None:
    """把渠道 / Query 写入指定版本。channels 可以是生成结果或前端提交体。"""
    for channel_index, channel in enumerate(channels):
        queries = [q for q in channel.queries if (q.query_text or "").strip()]
        db_channel = StrategyChannel(
            version_id=version.id,
            channel=channel.channel,
            enabled=bool(channel.enabled),
            target_countries=list(channel.target_countries or []),
            strategy_summary=(channel.strategy_summary or ""),
            sort_order=channel_index,
        )
        db.add(db_channel)
        db.flush()
        for query_index, query in enumerate(queries):
            db.add(
                StrategyQuery(
                    channel_id=db_channel.id,
                    query_text=query.query_text.strip(),
                    country_code=query.country_code,
                    language=query.language,
                    enabled=bool(query.enabled),
                    sort_order=getattr(query, "sort_order", query_index) or query_index,
                )
            )


def _create_draft_version(
    db: Session,
    strategy: SearchStrategy,
    generated: GeneratedStrategy,
    source: str,
) -> SearchStrategyVersion:
    version_number = _max_version_number(db, strategy.id) + 1
    version = SearchStrategyVersion(
        strategy_id=strategy.id,
        version=version_number,
        source=source,
        is_committed=False,
    )
    db.add(version)
    db.flush()
    _write_version_content(db, version, generated.channels)
    return version


def generate_strategy(
    db: Session, profile_id: str, generator: StrategyGenerator
) -> dict:
    """AI 生成。

    已有策略 -> 追加新的 Draft Version，不动 current_version_id、不降 status。
    无策略   -> 新建 Strategy(draft) + v1 Draft Version，current_version_id 留空。
    整个写入在一个事务内完成；AI 调用失败时不产生任何写入。
    """
    profile = get_profile(db, profile_id)

    # AI 调用在事务之外完成，失败不影响当前 Active Strategy
    generated = generator.generate(profile)

    strategy = db.scalars(
        select(SearchStrategy).where(SearchStrategy.profile_id == profile.id)
    ).first()

    try:
        if strategy is None:
            strategy = SearchStrategy(
                code=next_code(db, SearchStrategy, "STG"),
                profile_id=profile.id,
                status="draft",
                current_version_id=None,
            )
            db.add(strategy)
            db.flush()
            source = "ai_generate"
        else:
            source = "ai_regenerate"

        version = _create_draft_version(db, strategy, generated, source)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(strategy)
    return build_strategy_view(db, strategy, version=version)


def regenerate_strategy(db: Session, strategy_id: str, generator: StrategyGenerator) -> dict:
    """基于当前画像重新生成，产生新的 Draft Version。

    绝不修改 current_version_id 与 strategy.status —— 当前 Active 版本继续生效。
    """
    strategy = _load_strategy(db, strategy_id)
    profile = db.get(CustomerProfile, strategy.profile_id)
    if profile is None:
        raise NotFoundError("画像不存在")

    generated = generator.generate(profile)

    try:
        version = _create_draft_version(db, strategy, generated, "ai_regenerate")
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(strategy)
    return build_strategy_view(db, strategy, version=version)


def save_strategy(
    db: Session,
    strategy_id: str,
    *,
    channel_strategies: list[ChannelSearchStrategyIn],
    status: str,
    version: int,
    base_version: int,
) -> dict:
    """保存策略版本。

    status='draft'  -> 只提交该版本内容，不动 current_version_id / strategy.status
    status='active' -> 校验后切换 current_version_id 并置 strategy.status='active'
    两种情况都在同一事务内完成。
    """
    strategy = _load_strategy(db, strategy_id)

    current_base = _committed_version_number(db, strategy)
    if current_base != base_version:
        raise ConflictError(
            "该搜索策略已被其他用户更新，请刷新后重新操作。",
            code=STRATEGY_VERSION_CONFLICT,
        )

    # 渠道整体保留（含被 AI 判定为不适用、0 Query 的渠道）：
    # 那条 strategy_summary 是「为什么不走这个渠道」的判断依据，丢掉会让前端卡片消失。
    # 空文本 Query 在 _write_version_content 内逐条剔除，口径与前端 save() 一致。
    if status == "active" and not can_activate(channel_strategies):
        raise ValidationError(ACTIVATE_HINT, code=STRATEGY_NOT_ACTIVATABLE)

    target_version = db.scalars(
        select(SearchStrategyVersion)
        .where(SearchStrategyVersion.strategy_id == strategy.id)
        .where(SearchStrategyVersion.version == version)
    ).first()

    try:
        if target_version is None:
            target_version = SearchStrategyVersion(
                strategy_id=strategy.id,
                version=max(version, _max_version_number(db, strategy.id) + 1),
                source="manual_edit",
                is_committed=False,
            )
            db.add(target_version)
            db.flush()
        else:
            # 覆盖该版本的渠道内容（版本内可编辑，已激活版本由 base_version 保护）
            for channel in _load_version_channels(db, target_version.id):
                db.delete(channel)
            db.flush()

        _write_version_content(db, target_version, channel_strategies)
        target_version.is_committed = True

        if status == "active":
            strategy.current_version_id = target_version.id
            strategy.status = "active"
        # status='draft' 时刻意不改 strategy.status 与 current_version_id

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(strategy)
    return build_strategy_view(db, strategy)


def update_strategy_status(db: Session, strategy_id: str, status: str) -> dict:
    """启用 / 暂停。启用时必须通过完整校验。"""
    strategy = _load_strategy(db, strategy_id)

    if status == "active":
        version = _latest_version(db, strategy)
        channels = _load_version_channels(db, version.id) if version else []
        activatable = any(
            channel.enabled
            and any(q.enabled and q.query_text.strip() for q in channel.queries)
            for channel in channels
        )
        if not activatable:
            raise ValidationError(ACTIVATE_HINT, code=STRATEGY_NOT_ACTIVATABLE)
        if version is not None:
            version.is_committed = True
            strategy.current_version_id = version.id

    strategy.status = status
    db.commit()
    db.refresh(strategy)
    return build_strategy_view(db, strategy)
