import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.enums import ExtractionProviderName

JSONType = JSON().with_variant(JSONB(), "postgresql")


class DocumentExtraction(Base):
    """Raw extraction result for one completed processing job. Provenance-
    tagged (provider + version). Never read directly by the tax engine or any
    domain table — see docs/TAX_ENGINE_BOUNDARY.md. Field-level candidates
    live in `extracted_fields`; user confirmation into verified domain records
    is Phase 7's job, not this one's.
    """

    __tablename__ = "document_extractions"
    __table_args__ = (
        UniqueConstraint("document_processing_job_id", name="uq_document_extractions_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_processing_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_processing_jobs.id", ondelete="CASCADE"), nullable=False
    )
    tax_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_documents.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[ExtractionProviderName] = mapped_column(
        Enum(ExtractionProviderName, name="extraction_provider_name", native_enum=False, create_constraint=True),
        nullable=False,
    )
    provider_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_output: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document_processing_job: Mapped["DocumentProcessingJob"] = relationship()
    fields: Mapped[list["ExtractedField"]] = relationship(back_populates="document_extraction", cascade="all, delete-orphan")
