import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class InterestIncome(Base):
    """Verified savings/FD interest, sourced only from a confirmed extraction
    (docs/DATA_MODEL.md). One row per document_extraction, same shape/rules as
    SalaryIncome — see that model's docstring.
    """

    __tablename__ = "interest_income"
    __table_args__ = (
        UniqueConstraint("document_extraction_id", name="uq_interest_income_extraction"),
        CheckConstraint(
            "interest_amount IS NULL OR interest_amount >= 0", name="ck_interest_income_amount_non_negative"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tax_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_documents.id", ondelete="CASCADE"), nullable=False
    )
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False
    )
    interest_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    document_extraction: Mapped["DocumentExtraction"] = relationship()
