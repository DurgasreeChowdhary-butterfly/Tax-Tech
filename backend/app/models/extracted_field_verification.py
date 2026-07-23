import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, func, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.enums import VerificationAction

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ExtractedFieldVerification(Base):
    """Immutable, append-only review history for one extracted field — mirrors
    question_answers exactly: a CONFIRM or CORRECT is a new row (pointing back
    to what it supersedes), never an update. The original ExtractedField.raw_value
    is never touched by any of this. Exactly one row may be current per
    extracted_field — enforced by the partial unique index, not just app logic.
    """

    __tablename__ = "extracted_field_verifications"
    __table_args__ = (
        Index(
            "uq_extracted_field_verifications_current",
            "extracted_field_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extracted_field_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("extracted_fields.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[VerificationAction] = mapped_column(
        Enum(VerificationAction, name="verification_action", native_enum=False, create_constraint=True), nullable=False
    )
    # The confirmed value (CONFIRM: copy of raw_value at the time; CORRECT: the
    # user-provided replacement) — same JSON-string-for-money convention as
    # extracted_fields.raw_value, never a float.
    verified_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("extracted_field_verifications.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    extracted_field: Mapped["ExtractedField"] = relationship()
