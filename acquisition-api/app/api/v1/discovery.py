"""Search discovery runner API for Session B1."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_search_provider
from app.db import get_db
from app.providers.base import SearchProvider
from app.schemas.common import ApiResponse, ok
from app.schemas.discovery import DiscoveryRunPayload, DiscoveryRunResult
from app.services import discovery_service

router = APIRouter(prefix="/search-discovery", tags=["search-discovery"])


@router.post("/run", response_model=ApiResponse[DiscoveryRunResult])
def run_discovery(
    payload: DiscoveryRunPayload,
    db: Session = Depends(get_db),
    provider: SearchProvider = Depends(get_search_provider),
):
    result = discovery_service.run_discovery(
        db,
        provider=provider,
        strategy_id=payload.strategy_id,
        max_queries=payload.max_queries,
        results_per_query=payload.results_per_query,
        enterprise_target=payload.enterprise_target,
    )
    return ok(DiscoveryRunResult.model_validate(result))
