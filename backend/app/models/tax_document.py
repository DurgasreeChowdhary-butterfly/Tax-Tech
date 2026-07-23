import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import DocumentStatus, StorageProviderName


class TaxDocument(Base):
    """Uploaded file metadata + a private storage pointer. Never a public URL —
    `storage_key` is only ever resolved by a StorageProvider (see
    app/integrations/storage), never rendered as a URL to a client. The
    Document Service does not interpret file contents (no OCR/extraction here
    — that's Phase 6/7); `status` only ever reflects upload/deletion, never
    "processed" or "extracted", so upload completion can't be mistaken for
    extraction completion.
    """

    __tablename__ = "tax_documents"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_tax_documents_storage_key"),
        CheckConstraint("size_bytes > 0", name="ck_tax_documents_size_positive"),
        # Duplicate-content detection, enforced at the DB level too (not just
        # app logic): only one non-deleted document per (session, content
        # hash). Scoped to status='UPLOADED' so a deleted document's content
        # can be re-uploaded without conflict.
        Index(
            "uq_tax_documents_session_hash_active",
            "filing_session_id",
            "content_hash",
            unique=True,
            postgresql_where=text("status = 'UPLOADED'"),
            sqlite_where=text("status = 'UPLOADED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # Sanitized display metadata only — never used to derive a storage path.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_provider: Mapped[StorageProviderName] = mapped_column(
        Enum(StorageProviderName, name="storage_provider_name", native_enum=False, create_constraint=True),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    filing_session: Mapped["FilingSession"] = relationship()
