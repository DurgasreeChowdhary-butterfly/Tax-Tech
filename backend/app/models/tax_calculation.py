import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import TaxRegime


class TaxCalculation(Base):
    """One row per calculation run — never updated in place; a recalculation
    is always a new row (docs/DATA_MODEL.md). `is_current` + the partial
    unique index below mirror the ExtractedFieldVerification/QuestionAnswer
    append-only-history idiom: exactly one current calculation per
    (filing_session, regime), with `supersedes_id` chaining back through
    history. Old and new regime calculations are fully independent rows —
    never blended into one.

    `input_fingerprint` is a SHA-256 hex digest of a canonical, verified-
    inputs-only payload (see app/services/tax_calculation.py) — used solely
    to detect exact-retry idempotency. It contains no PAN, no document
    content, no storage keys, and is not reversible to the underlying
    amounts.
    """

    __tablename__ = "tax_calculations"
    __table_args__ = (
        Index(
            "uq_tax_calculations_current", "filing_session_id", "regime", unique=True,
            postgresql_where=text("is_current"), sqlite_where=text("is_current"),
        ),
        CheckConstraint("gross_total_income >= 0", name="ck_tax_calculations_gti_non_negative"),
        CheckConstraint("total_deductions_applied >= 0", name="ck_tax_calculations_deductions_non_negative"),
        CheckConstraint("taxable_income >= 0", name="ck_tax_calculations_taxable_income_non_negative"),
        CheckConstraint("tax_before_rebate >= 0", name="ck_tax_calculations_tax_before_rebate_non_negative"),
        CheckConstraint("rebate_amount >= 0", name="ck_tax_calculations_rebate_non_negative"),
        CheckConstraint("tax_after_rebate >= 0", name="ck_tax_calculations_tax_after_rebate_non_negative"),
        CheckConstraint("cess_amount >= 0", name="ck_tax_calculations_cess_non_negative"),
        CheckConstraint("total_tax_liability >= 0", name="ck_tax_calculations_total_tax_liability_non_negative"),
        CheckConstraint("total_tds_credit >= 0", name="ck_tax_calculations_tds_credit_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tax_rule_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_rule_sets.id", ondelete="RESTRICT"), nullable=False
    )
    regime: Mapped[TaxRegime] = mapped_column(
        Enum(TaxRegime, name="tax_regime", native_enum=False, create_constraint=True), nullable=False
    )
    calculation_engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_calculations.id", ondelete="SET NULL"), nullable=True
    )

    gross_total_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_deductions_applied: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_before_rebate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    rebate_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_after_rebate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cess_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_tax_liability: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_tds_credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_payable: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # negative = refund due

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    line_items: Mapped[list["CalculationLineItem"]] = relationship(
        back_populates="tax_calculation", cascade="all, delete-orphan"
    )
