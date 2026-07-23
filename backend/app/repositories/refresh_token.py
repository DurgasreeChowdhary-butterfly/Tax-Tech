import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        # SQLite (unlike PostgreSQL) does not round-trip tzinfo on
        # DateTime(timezone=True) columns — the value it round-trips is
        # already UTC (everything in this codebase is written in UTC), so
        # it's safe to just label it as such before comparing.
        return value.replace(tzinfo=timezone.utc)
    return value


def create_refresh_token(db: Session, *, user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime) -> RefreshToken:
    record = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def revoke_if_active(db: Session, jti: uuid.UUID) -> RefreshToken | None:
    """Atomically revokes the row for `jti` IFF it is not already revoked,
    in one UPDATE statement — no separate SELECT-then-UPDATE, so there is no
    window in which two concurrent callers can both observe "not yet
    revoked" and both proceed. Returns the now-revoked row if THIS call
    performed the revocation, or None if it was already revoked (by a
    concurrent caller, an earlier logout, or an earlier rotation) or never
    existed at all.

    Under READ COMMITTED (PostgreSQL's default), a second UPDATE racing on
    the same row blocks behind the first, then re-evaluates its WHERE clause
    against the just-committed state once unblocked — so at most one
    concurrent caller ever gets a non-None result back. This is what makes
    refresh rotation (services/auth.py::refresh_tokens) safe against two
    simultaneous requests presenting the same refresh token, and what
    prevents a logout/refresh race from both "succeeding" against the same
    token. Does not filter on expiry — an expired token is still marked
    revoked (harmless bookkeeping); callers that must reject expired tokens
    check `expires_at` on the returned row themselves.
    """
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
        .returning(RefreshToken)
    )
    record = db.execute(stmt).scalars().first()
    db.commit()
    return record


def is_expired(record: RefreshToken) -> bool:
    return _as_utc(record.expires_at) <= datetime.now(timezone.utc)
