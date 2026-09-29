"""客户画像 API，契约对齐 acquisition-web/src/api/profile.ts。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ApiResponse, PageResult, ok
from app.schemas.profile import CustomerProfileOut, ProfilePayload, ProfileStatusPayload
from app.services import profile_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_out(profile) -> CustomerProfileOut:
    data = CustomerProfileOut.model_validate(
        {
            **{c.name: getattr(profile, c.name) for c in profile.__table__.columns},
            "id": str(profile.id),
        }
    )
    return data


@router.get("", response_model=ApiResponse[PageResult[CustomerProfileOut]])
def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    profile_name: str | None = None,
    target_industry: str | None = None,
    target_country: str | None = None,
    is_enabled: bool | None = None,
    db: Session = Depends(get_db),
):
    items, total = profile_service.list_profiles(
        db,
        page=page,
        page_size=page_size,
        profile_name=profile_name,
        target_industry=target_industry,
        target_country=target_country,
        is_enabled=is_enabled,
    )
    return ok(
        PageResult[CustomerProfileOut](
            list=[_to_out(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[CustomerProfileOut])
def create_profile(payload: ProfilePayload, db: Session = Depends(get_db)):
    return ok(_to_out(profile_service.create_profile(db, payload)))


@router.get("/{profile_id}", response_model=ApiResponse[CustomerProfileOut])
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    return ok(_to_out(profile_service.get_profile(db, profile_id)))


@router.put("/{profile_id}", response_model=ApiResponse[CustomerProfileOut])
def update_profile(profile_id: str, payload: ProfilePayload, db: Session = Depends(get_db)):
    return ok(_to_out(profile_service.update_profile(db, profile_id, payload)))


@router.patch("/{profile_id}/status", response_model=ApiResponse[CustomerProfileOut])
def update_profile_status(
    profile_id: str, payload: ProfileStatusPayload, db: Session = Depends(get_db)
):
    return ok(_to_out(profile_service.update_profile_status(db, profile_id, payload.is_enabled)))
