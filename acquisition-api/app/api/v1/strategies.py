"""搜索策略 API，契约对齐 acquisition-web/src/api/strategy.ts。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_strategy_generator
from app.db import get_db
from app.generators.base import StrategyGenerator
from app.schemas.common import ApiResponse, PageResult, ok
from app.schemas.strategy import (
    SearchStrategyOut,
    StrategyGeneratePayload,
    StrategyStats,
    StrategyStatusPayload,
    StrategyUpdatePayload,
)
from app.services import strategy_service

router = APIRouter(prefix="/search-strategies", tags=["search-strategies"])


@router.get("", response_model=ApiResponse[PageResult[SearchStrategyOut]])
def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    profile_name: str | None = None,
    profile_id: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = strategy_service.list_strategies(
        db,
        page=page,
        page_size=page_size,
        profile_name=profile_name,
        profile_id=profile_id,
        channel=channel,
        status=status,
    )
    return ok(
        PageResult[SearchStrategyOut](
            list=[SearchStrategyOut.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/stats", response_model=ApiResponse[StrategyStats])
def strategy_stats(db: Session = Depends(get_db)):
    return ok(StrategyStats.model_validate(strategy_service.get_strategy_stats(db)))


@router.get("/{strategy_id}", response_model=ApiResponse[SearchStrategyOut])
def get_strategy(strategy_id: str, db: Session = Depends(get_db)):
    return ok(SearchStrategyOut.model_validate(strategy_service.get_strategy_view(db, strategy_id)))


@router.post("/generate", response_model=ApiResponse[SearchStrategyOut])
def generate_strategy(
    payload: StrategyGeneratePayload,
    db: Session = Depends(get_db),
    generator: StrategyGenerator = Depends(get_strategy_generator),
):
    view = strategy_service.generate_strategy(db, payload.profile_id, generator)
    return ok(SearchStrategyOut.model_validate(view))


@router.post("/{strategy_id}/regenerate", response_model=ApiResponse[SearchStrategyOut])
def regenerate_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    generator: StrategyGenerator = Depends(get_strategy_generator),
):
    view = strategy_service.regenerate_strategy(db, strategy_id, generator)
    return ok(SearchStrategyOut.model_validate(view))


@router.put("/{strategy_id}", response_model=ApiResponse[SearchStrategyOut])
def save_strategy(
    strategy_id: str, payload: StrategyUpdatePayload, db: Session = Depends(get_db)
):
    view = strategy_service.save_strategy(
        db,
        strategy_id,
        channel_strategies=payload.channel_strategies,
        status=payload.status,
        version=payload.version,
        base_version=payload.base_version,
    )
    return ok(SearchStrategyOut.model_validate(view))


@router.patch("/{strategy_id}/status", response_model=ApiResponse[SearchStrategyOut])
def update_strategy_status(
    strategy_id: str, payload: StrategyStatusPayload, db: Session = Depends(get_db)
):
    view = strategy_service.update_strategy_status(db, strategy_id, payload.status)
    return ok(SearchStrategyOut.model_validate(view))
