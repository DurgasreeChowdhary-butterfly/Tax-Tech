import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    """
    existing_by_code = {f.flag_code: f for f in get_all_flags_for_session(db, filing_session_id)}
    changed = False

    for code in active_flag_codes:
        existing = existing_by_code.get(code)
        if existing is None:
            db.add(FilingFlag(filing_session_id=filing_session_id, flag_code=code, is_active=True))
            changed = True
        elif not existing.is_active:
            existing.is_active = True
            changed = True

    for code in known_flag_codes - active_flag_codes:
        existing = existing_by_code.get(code)
        if existing is not None and existing.is_active:
            existing.is_active = False
            changed = True

    if changed:
        db.commit()

    return get_all_flags_for_session(db, filing_session_id)
