import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class RefreshToken(Base):
    """Server-side record of one issued refresh token, keyed by the JWT's own
    `jti` claim — NOT the token string itself (the signature already proves
    possession; this table exists only so a refresh token can be revoked
    before its natural expiry, which a stateless JWT alone can't support).

    Enables: logout (revoke on demand), rotation (the previous refresh token
    is revoked the moment it's used to mint a new pair, so a stolen-but-
    already-used refresh token is useless), and forcing a session to end
    server-side. Access tokens are intentionally NOT tracked here — they are
    short-lived (see Settings.access_token_expire_minutes) and stateless by
    design; logout revokes future refreshes, not an already-issued access
    token, which simply expires on its own shortly after.

    Row growth / cleanup: rows are never deleted by any code path in this
    phase — expired and revoked rows accumulate indefinitely. This is a
    deliberate Phase 11 deferral, not an oversight: this codebase has no
    background-job infrastructure yet (docs/IMPLEMENTATION_PLAN.md notes
    "background job infra with Redis" as a later, not-yet-detailed phase),
    and adding one solely to prune this table would be scope creep ahead of
    that phase. `expires_at` and `revoked_at` are both indexable, sufficient
    for a future scheduled `DELETE FROM refresh_tokens WHERE expires_at <
    :cutoff` (or similar) once real background-job infra exists. Until then,
    row count grows at one row per login/refresh per user — acceptable at
    V1's scale, revisit if/when it isn't.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship()
