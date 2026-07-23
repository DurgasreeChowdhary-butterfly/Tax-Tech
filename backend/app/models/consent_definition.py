import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import ConsentDefinitionStatus


class ConsentDefinition(Base):
    """Versioned text/purpose of one consent type (e.g. DATA_PROCESSING),
    mirroring the QuestionnaireVersion/TaxRuleSet DRAFT->PUBLISHED pattern
    (docs/DATA_MODEL.md). A published version is immutable — enforced at the
    database level via a trigger added in the Phase 10 migration, matching
    the existing questionnaire/tax-rule-set immutability pattern exactly.

    `code` identifies the consent type across versions (e.g. re-publishing a
    reworded DATA_PROCESSING consent creates a new row with version_number+1,
    never edits the old one). `is_required` marks it as a precondition for
    the actions documented in docs/TAX_ENGINE_BOUNDARY.md /
    docs/IMPLEMENTATION_PLAN.md Phase 10 (e.g. document upload/processing);
    required-consent resolution (app/services/consent.py) always reads the
    latest PUBLISHED version per code — never a client-supplied version.
    """

    __tablename__ = "consent_definitions"
    __table_args__ = (UniqueConstraint("code", "version_number", name="uq_consent_definitions_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    status: Mapped[ConsentDefinitionStatus] = mapped_column(
        Enum(ConsentDefinitionStatus, name="consent_definition_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=ConsentDefinitionStatus.DRAFT,
        server_default=ConsentDefinitionStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user_consents: Mapped[list["UserConsent"]] = relationship(back_populates="consent_definition")
