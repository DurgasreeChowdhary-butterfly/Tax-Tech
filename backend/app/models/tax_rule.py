import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.enums import TaxRegime, TaxRuleType

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. the SQLite test path).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class TaxRule(Base):
    """One slab/rebate/surcharge/cess/deduction rule belonging to a tax_rule_set
    (docs/DATA_MODEL.md). `parameters` holds rule-type-specific figures as
    JSON-safe values — monetary figures are Decimal-parseable strings, never
    float (same convention as extracted_fields/question_answers currency
    handling); parsed to Decimal only at the point of use in the calculation
    engine (Phase 9).
    """

    __tablename__ = "tax_rules"
    __table_args__ = (UniqueConstraint("tax_rule_set_id", "regime", "code", name="uq_tax_rules_set_regime_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_rule_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_rule_sets.id", ondelete="CASCADE"), nullable=False
    )
    regime: Mapped[TaxRegime] = mapped_column(
        Enum(TaxRegime, name="tax_regime", native_enum=False, create_constraint=True), nullable=False
    )
    rule_type: Mapped[TaxRuleType] = mapped_column(
        Enum(TaxRuleType, name="tax_rule_type", native_enum=False, create_constraint=True), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    parameters: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tax_rule_set: Mapped["TaxRuleSet"] = relationship(back_populates="tax_rules")
