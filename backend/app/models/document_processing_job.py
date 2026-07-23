import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import DocumentProcessingJobStatus, ExtractionFailureCode, ExtractionProviderName


class DocumentProcessingJob(Base):
    """Async job tracking for OCR/AI processing of a tax_document.

    Runs synchronously/in-process for now (per docs/IMPLEMENTATION_PLAN.md
    Phase 6) — the full PENDING -> RUNNING -> COMPLETED/FAILED state machine
    is modeled regardless, so a real queue-backed worker can be dropped in
    later (Phase 6 goal) without a schema change.

    `error_code` is a small, fixed, safe-to-expose classification — it is the
    ONLY failure information any API schema may serialize. `error_detail` is a
    bounded, sanitized diagnostic string (currently: the exception class name
    only) for internal/operator use — never the raw exception message, storage
    keys, filesystem paths, provider secrets/tokens, PAN, financial values, or
    document content, since exception messages are unbounded and can contain
    any of those. No Pydantic response schema may ever serialize this column.
    See app/engines/extraction/failure_classification.py.
    """

    __tablename__ = "document_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tax_documents.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[ExtractionProviderName] = mapped_column(
        Enum(ExtractionProviderName, name="extraction_provider_name", native_enum=False, create_constraint=True),
        nullable=False,
    )
    status: Mapped[DocumentProcessingJobStatus] = mapped_column(
        Enum(DocumentProcessingJobStatus, name="document_processing_job_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=DocumentProcessingJobStatus.PENDING,
        server_default=DocumentProcessingJobStatus.PENDING.value,
    )
    error_code: Mapped[ExtractionFailureCode | None] = mapped_column(
        Enum(ExtractionFailureCode, name="extraction_failure_code", native_enum=False, create_constraint=True),
        nullable=True,
    )
    # Internal-only. Never serialize this via any API schema.
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tax_document: Mapped["TaxDocument"] = relationship()
