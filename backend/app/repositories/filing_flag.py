import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.enums import ActorType, AuditEventCode
from app.models.filing_flag import FilingFlag


def get_all_flags_for_session(db: Session, filing_session_id: uuid.UUID) -> list[FilingFlag]:
    stmt = select(FilingFlag).where(FilingFlag.filing_session_id == filing_session_id)
    return list(db.execute(stmt).scalars().all())


def reconcile_flags(db: Session, filing_session_id: uuid.UUID, active_flag_codes: set[str], known_flag_codes: set[str]) -> list[FilingFlag]:
    """Bring persisted filing_flags in line with the currently-supported set.

    Only rows whose flag_code is in `known_flag_codes` (i.e. emittable by some
    rule in the session's bound questionnaire version) are touched — flags set
    by any other subsystem are left completely alone. Idempotent: calling this
    again with the same `active_flag_codes` makes no further writes.

    Each genuine inactive->active or active->inactive flip stages a
    FILING_FLAG_ACTIVATED/DEACTIVATED audit event in the same transaction as
    the flip (never on the no-op branches, so a repeated reconciliation with
    no effective state change emits no duplicate transition, and an
    inactive->active->inactive->active sequence across separate calls
    produces one historical event per real transition). This recompute is a
    deterministic function of already-audited answers/rules, not itself a
    distinct user action, so its actor is SYSTEM.
    """
    existing_by_code = {f.flag_code: f for f in get_all_flags_for_session(db, filing_session_id)}
    changed = False

    for code in active_flag_codes:
        existing = existing_by_code.get(code)
        if existing is None:
            flag = FilingFlag(filing_session_id=filing_session_id, flag_code=code, is_active=True)
            db.add(flag)
            db.flush()
            audit_service.stage_event(
                db,
                event_code=AuditEventCode.FILING_FLAG_ACTIVATED,
                actor_type=ActorType.SYSTEM,
                filing_session_id=filing_session_id,
                subject_type="filing_flag",
                subject_id=flag.id,
                metadata={"flag_code": code},
            )
            changed = True
        elif not existing.is_active:
            existing.is_active = True
            audit_service.stage_event(
                db,
                event_code=AuditEventCode.FILING_FLAG_ACTIVATED,
                actor_type=ActorType.SYSTEM,
                filing_session_id=filing_session_id,
                subject_type="filing_flag",
                subject_id=existing.id,
                metadata={"flag_code": code},
            )
            changed = True

    for code in known_flag_codes - active_flag_codes:
        existing = existing_by_code.get(code)
        if existing is not None and existing.is_active:
            existing.is_active = False
            audit_service.stage_event(
                db,
                event_code=AuditEventCode.FILING_FLAG_DEACTIVATED,
                actor_type=ActorType.SYSTEM,
                filing_session_id=filing_session_id,
                subject_type="filing_flag",
                subject_id=existing.id,
                metadata={"flag_code": code},
            )
            changed = True

    if changed:
        db.commit()

    return get_all_flags_for_session(db, filing_session_id)
