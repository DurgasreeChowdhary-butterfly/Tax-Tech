import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import TaxRuleSetStatus


class TaxRuleSet(Base):
    """One per assessment year + engine version, published immutably — mirrors
    QuestionnaireVersion's versioning pattern (docs/DATA_MODEL.md). Immutability
    of PUBLISHED rows (and their tax_rules) is enforced at the database level on
    PostgreSQL via triggers added in the Phase 8 migration; the SQLite test path
    relies on the service-layer guard instead (app/engines/tax/lifecycle.py).
    """

    __tablename__ = "tax_rule_sets"
    __table_args__ = (
        UniqueConstraint("assessment_year", "engine_version", name="uq_tax_rule_sets_ay_engine_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_year: Mapped[str] = mapped_column(String(9), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[TaxRuleSetStatus] = mapped_column(
        Enum(TaxRuleSetStatus, name="tax_rule_set_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=TaxRuleSetStatus.DRAFT,
        server_default=TaxRuleSetStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tax_rules: Mapped[list["TaxRule"]] = relationship(back_populates="tax_rule_set", cascade="all, delete-orphan")
