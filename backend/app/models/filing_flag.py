import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class FilingFlag(Base):
    """A named decision fact tied to a filing session (e.g. REVIEW_REQUIRED,
    FREELANCE_INCOME_DETECTED). Reflects CURRENT effective state only.

    This is NOT a transition log: `updated_at` records only the most recent
    flip, so an inactive -> active -> inactive -> active sequence collapses to
    "currently active, last changed at <t3>" — intermediate transitions are
    not retrievable from this row. That is intentional, not an oversight: the
    full history is not lost, because every transition is a deterministic
    function of the (already immutable, append-only) `question_answers`
    history and the (already immutable-once-published) `question_rules` — it
    is reconstructible by replaying the decision engine over historical answer
    states. An explicit, queryable event-level record of each transition is
    `audit_logs`' job (Phase 10 — see docs/DATA_MODEL.md), not this table's.
    """

    __tablename__ = "filing_flags"
    __table_args__ = (UniqueConstraint("filing_session_id", "flag_code", name="uq_filing_flags_session_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    flag_code: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    filing_session: Mapped["FilingSession"] = relationship(back_populates="filing_flags")
