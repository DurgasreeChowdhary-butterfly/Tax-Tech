import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class FilingFlag(Base):
    """A named decision fact tied to a filing session (e.g. REVIEW_REQUIRED,
    FREELANCE_INCOME_DETECTED). Reflects CURRENT effective state, reconciled by
    the Decision Engine from current answers — not an append-only log. One row
    per (filing_session, flag_code); reconciliation flips `is_active` on the
    same row rather than creating duplicates.
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
