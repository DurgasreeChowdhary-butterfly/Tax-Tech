import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. the SQLite test path).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class CalculationLineItem(Base):
    """One itemized step of a tax_calculation (docs/DATA_MODEL.md) — income
    components, deduction CLAIMED/ELIGIBLE/APPLIED amounts, per-slab tax,
    rebate, cess, credits, net payable. `step_code` is a plain string (not a
    DB enum) because it is tied to the versioned calculation engine/rule
    content, the same convention as extracted_fields.field_name. `metadata`
    holds only rule codes/rates for explainability — never PAN, document
    content, or other sensitive values.
    """

    __tablename__ = "calculation_line_items"
    __table_args__ = (
        UniqueConstraint("tax_calculation_id", "sequence_index", name="uq_calc_line_items_calc_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_calculation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_calculations.id", ondelete="CASCADE"), nullable=False
    )
    step_code: Mapped[str] = mapped_column(String(60), nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    step_metadata: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tax_calculation: Mapped["TaxCalculation"] = relationship(back_populates="line_items")
