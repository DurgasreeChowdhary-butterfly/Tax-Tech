import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class SalaryIncome(Base):
    """Verified salary figures for one employer, sourced only from a confirmed
    Form16 extraction (docs/DATA_MODEL.md). One row per document_extraction —
    Phase 7 has no `employers` table, so each Form16 extraction stands in for
    "one employer's data" directly. Columns start NULL and are filled in one
    at a time as each corresponding extracted_field is confirmed/corrected;
    never populated except through the verification workflow
    (app/services/verification.py).
    """

    __tablename__ = "salary_income"
    __table_args__ = (
        UniqueConstraint("document_extraction_id", name="uq_salary_income_extraction"),
        CheckConstraint("gross_salary IS NULL OR gross_salary >= 0", name="ck_salary_income_gross_salary_non_negative"),
        CheckConstraint("tds_deducted IS NULL OR tds_deducted >= 0", name="ck_salary_income_tds_deducted_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tax_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_documents.id", ondelete="CASCADE"), nullable=False
    )
    # Provenance: which extraction produced this verified record.
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False
    )
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gross_salary: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tds_deducted: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    document_extraction: Mapped["DocumentExtraction"] = relationship()
