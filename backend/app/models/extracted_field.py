import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ExtractedField(Base):
    """A single candidate field value produced by an extraction, with a
    confidence score. Raw and unverified — never read by the tax engine.
    Gets linked to a verified domain record only once a human confirms it
    (Phase 7); no such link column exists yet because the domain tables it
    would point to (salary_income, etc.) don't exist until then.
    """

    __tablename__ = "extracted_fields"
    __table_args__ = (CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_extracted_fields_confidence_range"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document_extraction: Mapped["DocumentExtraction"] = relationship(back_populates="fields")
