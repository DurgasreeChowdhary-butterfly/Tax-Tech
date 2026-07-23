import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import ActorType, AuditEventCode

# Intentionally no update/delete function in this module — audit_logs is
# append-only at the application layer (see app/audit/service.py) and,
# on PostgreSQL, at the database layer too (Phase 10 migration trigger).


def add_event(
    db: Session,
    *,
    event_code: AuditEventCode,
    actor_type: ActorType,
    actor_user_id: uuid.UUID | None,
    filing_session_id: uuid.UUID | None,
    subject_type: str | None,
    subject_id: uuid.UUID | None,
    metadata: dict | None,
) -> AuditLog:
    """Adds and flushes (does NOT commit) an audit_logs row.

    Callers stage this immediately before the `db.commit()` that persists the
    domain change it documents, so both succeed or roll back together as one
    transaction (docs/IMPLEMENTATION_PLAN.md Phase 10 transactional-
    consistency requirement) — this function must never call db.commit()
    itself.
    """
    event = AuditLog(
        event_code=event_code,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type=subject_type,
        subject_id=subject_id,
        event_metadata=metadata,
    )
    db.add(event)
    db.flush()
    return event


def list_for_filing_session(db: Session, filing_session_id: uuid.UUID) -> list[AuditLog]:
    """Internal/diagnostic read path only — no API route exposes this
    unrestricted (CLAUDE.md: no broad unrestricted audit-log API to
    taxpayers). Used by tests and future admin tooling."""
    # created_at only (no secondary tiebreaker) — mirrors every other
    # append-only history query in this codebase (get_answer_history,
    # get_verification_history, get_calculation_history), which rely on the
    # same single-column ordering for chronological results.
    stmt = select(AuditLog).where(AuditLog.filing_session_id == filing_session_id).order_by(AuditLog.created_at)
    return list(db.execute(stmt).scalars().all())
