"""客户画像业务逻辑。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PROFILE_NAME_DUPLICATED
from app.models import CustomerProfile
from app.schemas.profile import ProfilePayload
from app.services.code_gen import next_code


def _to_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise NotFoundError("画像不存在") from exc


def get_profile(db: Session, profile_id: str) -> CustomerProfile:
    profile = db.get(CustomerProfile, _to_uuid(profile_id))
    if profile is None:
        raise NotFoundError("画像不存在")
    return profile


def list_profiles(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    profile_name: str | None = None,
    target_industry: str | None = None,
    target_country: str | None = None,
    is_enabled: bool | None = None,
) -> tuple[list[CustomerProfile], int]:
    stmt = select(CustomerProfile)
    count_stmt = select(func.count()).select_from(CustomerProfile)

    conditions = []
    if profile_name:
        conditions.append(CustomerProfile.profile_name.ilike(f"%{profile_name.strip()}%"))
    if target_industry:
        conditions.append(CustomerProfile.target_industries.any(target_industry))
    if target_country:
        conditions.append(CustomerProfile.target_countries.any(target_country))
    if is_enabled is not None:
        conditions.append(CustomerProfile.is_enabled.is_(is_enabled))

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(CustomerProfile.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all()), total


def create_profile(db: Session, payload: ProfilePayload) -> CustomerProfile:
    profile = CustomerProfile(
        code=next_code(db, CustomerProfile, "PRF"),
        **payload.model_dump(),
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("画像名称已存在", code=PROFILE_NAME_DUPLICATED) from exc
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile_id: str, payload: ProfilePayload) -> CustomerProfile:
    profile = get_profile(db, profile_id)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("画像名称已存在", code=PROFILE_NAME_DUPLICATED) from exc
    db.refresh(profile)
    return profile


def update_profile_status(db: Session, profile_id: str, is_enabled: bool) -> CustomerProfile:
    """暂停画像不删除任何历史数据，只阻止后续自动任务产生。"""
    profile = get_profile(db, profile_id)
    profile.is_enabled = is_enabled
    db.commit()
    db.refresh(profile)
    return profile
