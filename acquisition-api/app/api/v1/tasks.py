"""Acquisition task API, aligned with acquisition-web/src/api/task.ts."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_search_provider
from app.db import get_db
from app.providers.base import SearchProvider
from app.schemas.common import ApiResponse, PageResult, ok
from app.schemas.task import AcquisitionTaskCreate, AcquisitionTaskOut, AcquisitionTaskStatsOut
from app.services import task_service

router = APIRouter(prefix="/acquisition-tasks", tags=["acquisition-tasks"])


@router.get("", response_model=ApiResponse[PageResult[AcquisitionTaskOut]])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    task_name: str | None = None,
    profile_name: str | None = None,
    strategy_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = task_service.list_tasks(
        db,
        page=page,
        page_size=page_size,
        task_name=task_name,
        profile_name=profile_name,
        strategy_id=strategy_id,
        status=status,
    )
    return ok(
        PageResult[AcquisitionTaskOut](
            list=[AcquisitionTaskOut.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/stats", response_model=ApiResponse[AcquisitionTaskStatsOut])
def task_stats(db: Session = Depends(get_db)):
    return ok(task_service.get_task_stats(db))


@router.post("", response_model=ApiResponse[AcquisitionTaskOut])
def create_task(payload: AcquisitionTaskCreate, db: Session = Depends(get_db)):
    return ok(AcquisitionTaskOut.model_validate(task_service.create_task(db, payload)))


@router.get("/{task_id}", response_model=ApiResponse[AcquisitionTaskOut])
def get_task(task_id: str, db: Session = Depends(get_db)):
    return ok(AcquisitionTaskOut.model_validate(task_service.get_task_view(db, task_id)))


@router.post("/{task_id}/run", response_model=ApiResponse[AcquisitionTaskOut])
def run_task(
    task_id: str,
    db: Session = Depends(get_db),
    provider: SearchProvider = Depends(get_search_provider),
):
    return ok(AcquisitionTaskOut.model_validate(task_service.run_task(db, task_id, provider)))
