import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.deduction import Deduction
from app.models.enums import ActorType, AuditEventCode


def get_deduction_claim(db: Session, filing_session_id: uuid.UUID, code: str) -> Deduction | None:
    stmt = select(Deduction).where(Deduction.filing_session_id == filing_session_id, Deduction.code == code)
    return db.execute(stmt).scalars().first()


def list_deduction_claims_for_session(db: Session, filing_session_id: uuid.UUID) -> list[Deduction]:
    stmt = select(Deduction).where(Deduction.filing_session_id == filing_session_id).order_by(Deduction.code)
    return list(db.execute(stmt).scalars().all())


def upsert_deduction_claim(
    db: Session, filing_session_id: uuid.UUID, code: str, claimed_amount: Decimal, *, actor_user_id: uuid.UUID
) -> Deduction:
    """Idempotent: an exact-value re-claim leaves the row untouched (no
    spurious updated_at bump, no audit event). A genuine change updates
    claimed_amount in place — deduction claims are simple manual entries, not
    an append-only history (unlike tax_calculations/question_answers) — and
    stages a DEDUCTION_CLAIMED (new code) or DEDUCTION_CHANGED (existing
    code, new amount) event in the same transaction. `code` (e.g.
    "SECTION_80C") is the only audit metadata — claimed_amount is a financial
    value and is never included.
    """
    existing = get_deduction_claim(db, filing_session_id, code)
    if existing is not None:
        if existing.claimed_amount == claimed_amount:
            return existing
        existing.claimed_amount = claimed_amount
        audit_service.stage_event(
            db,
            event_code=AuditEventCode.DEDUCTION_CHANGED,
            actor_type=ActorType.USER,
            actor_user_id=actor_user_id,
            filing_session_id=filing_session_id,
            subject_type="deduction",
            subject_id=existing.id,
            metadata={"code": code},
        )
        db.commit()
        db.refresh(existing)
        return existing

    row = Deduction(filing_session_id=filing_session_id, code=code, claimed_amount=claimed_amount)
    db.add(row)
    db.flush()
    audit_service.stage_event(
        db,
        event_code=AuditEventCode.DEDUCTION_CLAIMED,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type="deduction",
        subject_id=row.id,
        metadata={"code": code},
    )
    db.commit()
    db.refresh(row)
    return row
