import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class Deduction(Base):
    """A claimed deduction entry (docs/DATA_MODEL.md) — direct manual entry,
    like salary_income's "confirmed Form16 extraction or manual entry": there
    is no extraction candidate for a deduction claim in V1, so the claim
    itself is the verified input. Only `claimed_amount` lives here; eligible/
    applied amounts are computed fresh at calculation time (never cached —
    recompute-not-accumulate) and recorded as calculation_line_items instead,
    per docs/TAX_ENGINE_BOUNDARY.md's CLAIMED/ELIGIBLE/APPLIED distinction.
    """

    __tablename__ = "deductions"
    __table_args__ = (
        UniqueConstraint("filing_session_id", "code", name="uq_deductions_session_code"),
        CheckConstraint("claimed_amount >= 0", name="ck_deductions_claimed_amount_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    claimed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
