"""Single-enterprise, restart-safe C0 → C1 → C2 orchestration."""

import uuid
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tldextract import TLDExtract

from app.config import Settings
from app.core.errors import AppError
from app.models import EnterpriseMarketingHandoff
from app.schemas.marketing_handoff import MarketingHandoffOut
from app.services import company_service, research_service


_domain_parts = TLDExtract(suffix_list_urls=())
LEASE = timedelta(minutes=6)  # Longer than any single Marketing HTTP step (240 seconds).


def _domain(value: str | None) -> str:
    parts = _domain_parts(value or "")
    return f"{parts.domain}.{parts.suffix}" if parts.domain and parts.suffix else ""


def _result(row: EnterpriseMarketingHandoff) -> MarketingHandoffOut:
    return MarketingHandoffOut(
        enterprise_id=str(row.enterprise_id), status=row.status, stage=row.stage,
        research_id=row.research_id, marketing_customer_id=row.marketing_customer_id,
        job_id=row.job_id, failure_code=row.failure_code,
        attempt_count=row.attempt_count, updated_at=row.updated_at,
    )


def _current(db: Session, enterprise_id: uuid.UUID) -> EnterpriseMarketingHandoff | None:
    # SessionLocal uses expire_on_commit=False; bypass any cached row after SQL UPDATE.
    return db.get(EnterpriseMarketingHandoff, enterprise_id, populate_existing=True)


def get_status(db: Session, enterprise_id: str) -> MarketingHandoffOut:
    enterprise = company_service.get_company(db, enterprise_id)
    row = _current(db, enterprise.id)
    if row is None:
        return MarketingHandoffOut(enterprise_id=str(enterprise.id), status="not_started", stage="research")
    return _result(row)


def _save(db: Session, enterprise_id: uuid.UUID, claim_id: uuid.UUID, **changes):
    values = {**changes, "updated_at": datetime.now(timezone.utc)}
    result = db.execute(update(EnterpriseMarketingHandoff).where(
        EnterpriseMarketingHandoff.enterprise_id == enterprise_id,
        EnterpriseMarketingHandoff.run_id == claim_id,
        EnterpriseMarketingHandoff.status == "running",
    ).values(**values).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise AppError("交接运行权已变化，请查询状态", status_code=409, code="handoff_run_changed")
    db.commit()
    return _current(db, enterprise_id)


def _progress(db, enterprise_id, run_id, stage, **changes):
    return _save(db, enterprise_id, run_id, stage=stage,
                 lease_until=datetime.now(timezone.utc) + LEASE, **changes)


def _finish(db, enterprise_id, run_id, status, stage, failure_code=None, **changes):
    if failure_code is not None and not re.fullmatch(r"[A-Za-z0-9_]{1,80}", str(failure_code)):
        failure_code = "upstream_failure"
    return _save(db, enterprise_id, run_id, status=status, stage=stage,
                 failure_code=failure_code, lease_until=None, run_id=None, **changes)


def trigger(db: Session, enterprise_id: str, settings: Settings,
            *, retry_blocked: bool = False) -> MarketingHandoffOut:
    enterprise = company_service.get_company(db, enterprise_id)
    row = _current(db, enterprise.id)
    if row is None:
        db.add(EnterpriseMarketingHandoff(enterprise_id=enterprise.id, status="pending",
                                          stage="research", attempt_count=0))
        try:
            db.commit()
        except IntegrityError:  # Another process inserted this Enterprise at the same time.
            db.rollback()
        row = _current(db, enterprise.id)
    if row.status == "queued":
        return _result(row)
    if row.status == "blocked" and not retry_blocked:
        return _result(row)

    now = datetime.now(timezone.utc)
    run_id = uuid.uuid4()
    claim = db.execute(update(EnterpriseMarketingHandoff).where(
        EnterpriseMarketingHandoff.enterprise_id == enterprise.id,
        EnterpriseMarketingHandoff.status != "queued",
        or_(EnterpriseMarketingHandoff.status != "running",
            EnterpriseMarketingHandoff.lease_until < now),
    ).values(status="running", run_id=run_id, lease_until=now + LEASE,
             attempt_count=EnterpriseMarketingHandoff.attempt_count + 1,
             failure_code=None, updated_at=now).execution_options(synchronize_session=False))
    db.commit()
    if claim.rowcount != 1:
        return _result(_current(db, enterprise.id))

    stage = "research"
    try:
        sources = sorted(enterprise.discovery_sources, key=lambda item: item.discovered_at, reverse=True)
        if not sources or not enterprise.domain or not enterprise.company_name:
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage, "missing_discovery_evidence"))
        source = sources[0]
        body = {
            "source": "liverno", "source_id": str(enterprise.id),
            "domain": enterprise.domain, "candidate_name": enterprise.company_name,
            "evidence_url": source.result_url, "discovered_at": source.discovered_at.isoformat(),
            "country": enterprise.country, "industry": enterprise.industry,
        }
        _progress(db, enterprise.id, run_id, stage)
        record = research_service.get_record(str(enterprise.id), settings)
        if record is None:
            record = research_service.intake_research(str(enterprise.id), body, settings)
        research_id = record["id"]
        _progress(db, enterprise.id, run_id, stage, research_id=research_id)
        if record["status"] in ("received", "researching", "company_matched"):
            return _result(_finish(db, enterprise.id, run_id, "waiting_research", stage))
        if record["status"] not in ("completed", "no_contact"):
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage,
                                   f"research_{record['status']}"))

        stage = "qualification"
        _progress(db, enterprise.id, run_id, stage)
        if record.get("qualification", {}).get("status") == "not_started":
            record = research_service.qualify_research(research_id, str(enterprise.id), settings)
        qualification = record.get("qualification") or {}
        if qualification.get("status") in ("researching_website", "qualifying"):
            return _result(_finish(db, enterprise.id, run_id, "waiting_qualification", stage))
        if qualification.get("status") != "qualified" or qualification.get("qualified") is not True:
            reason = qualification.get("reason_code") or qualification.get("status") or "invalid_qualification"
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage, reason))
        company = record.get("company") or {}
        contacts = record.get("contacts") or []
        root = _domain(enterprise.domain)
        if not root or _domain(record.get("domain")) != root or _domain(company.get("domain")) != root:
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage, "identity_domain_mismatch"))
        if not any(isinstance(contact, dict) and contact.get("person_id") and
                   contact.get("has_email") is True and
                   contact.get("email_status") in ("verified", "valid") for contact in contacts):
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage, "missing_verified_contact"))

        stage = "handoff"
        _progress(db, enterprise.id, run_id, stage)
        handoff = research_service.get_handoff(str(enterprise.id), settings)
        if handoff and handoff["status"] == "preparing":
            return _result(_finish(db, enterprise.id, run_id, "waiting_handoff", stage,
                                   marketing_customer_id=handoff.get("marketingCustomerId")))
        if handoff and handoff["status"] in ("failed", "blocked_duplicate") and not retry_blocked:
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage,
                                   handoff.get("failureReason") or handoff["status"],
                                   marketing_customer_id=handoff.get("marketingCustomerId")))
        if handoff is None or handoff["status"] != "queued":
            handoff = research_service.create_handoff(str(enterprise.id), settings)
        if handoff.get("researchId") != research_id or handoff.get("qualificationStatus") != "qualified" or \
                handoff.get("fumengCustomerId") not in (None, ""):
            return _result(_finish(db, enterprise.id, run_id, "blocked", stage,
                                   "handoff_identity_mismatch"))
        customer_id = handoff.get("marketingCustomerId")
        job_id = handoff.get("jobId")
        if handoff["status"] == "queued":
            if not isinstance(customer_id, str) or not customer_id or \
                    not isinstance(job_id, str) or not job_id:
                return _result(_finish(db, enterprise.id, run_id, "retryable", stage,
                                       "handoff_missing_ids"))
            return _result(_finish(db, enterprise.id, run_id, "queued", stage,
                                   research_id=research_id, marketing_customer_id=customer_id,
                                   job_id=job_id))
        status = "waiting_handoff" if handoff["status"] in ("received", "preparing") else "blocked"
        return _result(_finish(db, enterprise.id, run_id, status, stage,
                               handoff.get("failureReason") or handoff["status"],
                               marketing_customer_id=customer_id))
    except AppError as exc:
        if exc.code == "handoff_run_changed":
            raise
        status = "blocked" if exc.code in ("QUALIFICATION_REQUIRED", "IDENTITY_DOMAIN_MISMATCH") else "retryable"
        return _result(_finish(db, enterprise.id, run_id, status, stage, exc.code))
    except Exception:
        _finish(db, enterprise.id, run_id, "retryable", stage, "internal_error")
        raise
