import hashlib
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.storage.base import StorageObjectNotFoundError, StorageProvider
from app.integrations.storage.provider import get_storage_provider
from app.models.enums import DocumentStatus, StorageProviderName
from app.models.tax_document import TaxDocument
from app.repositories import tax_document as tax_document_repo
from app.repositories.filing_session import get_filing_session
from app.services import consent as consent_service
from app.services.document_errors import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    StorageObjectMissingError,
)
from app.services.document_validation import sanitize_filename, validate_supported_content


def _get_filing_session_or_raise(db: Session, filing_session_id: uuid.UUID):
    filing_session = get_filing_session(db, filing_session_id)
    if filing_session is None:
        raise ValueError(f"Filing session {filing_session_id} not found")
    return filing_session


def _storage_key_for(filing_session_id: uuid.UUID, document_id: uuid.UUID) -> str:
    # Fully server-generated: session id + a freshly generated document id.
    # The client-supplied filename never contributes to this path.
    return f"filing-sessions/{filing_session_id}/{document_id}"


def upload_document(
    db: Session,
    filing_session_id: uuid.UUID,
    *,
    original_filename: str,
    content: bytes,
    storage: StorageProvider | None = None,
) -> tuple[TaxDocument, bool]:
    """Returns (document, is_duplicate).

    Duplicate uploads (identical content hash, same filing session, among
    non-deleted documents) are idempotent: no new storage object or DB row is
    written — the existing document is returned as-is, matching this
    project's established safe-retry philosophy for mobile network conditions.
    """
    filing_session = _get_filing_session_or_raise(db, filing_session_id)
    # Phase 10 exit criterion: consent must be recorded before document
    # upload/processing proceeds. Raises MissingRequiredConsentError (never
    # silently proceeds) if any required consent isn't currently accepted for
    # this exact filing session.
    consent_service.assert_required_consents_accepted(db, filing_session_id)

    if not content:
        raise EmptyFileError()

    max_bytes = get_settings().max_upload_size_bytes
    if len(content) > max_bytes:
        raise FileTooLargeError(len(content), max_bytes)

    content_type = validate_supported_content(content)
    content_hash = hashlib.sha256(content).hexdigest()

    existing = tax_document_repo.get_active_document_by_hash(db, filing_session_id, content_hash)
    if existing is not None:
        return existing, True

    storage = storage or get_storage_provider()
    document_id = uuid.uuid4()
    storage_key = _storage_key_for(filing_session_id, document_id)

    # Storage write happens before the DB row so a DB row can never point to
    # content that was never actually written.
    storage.save(storage_key, content)

    try:
        document = tax_document_repo.create_document(
            db,
            document_id=document_id,
            filing_session_id=filing_session_id,
            original_filename=sanitize_filename(original_filename),
            storage_key=storage_key,
            storage_provider=StorageProviderName.LOCAL_FILESYSTEM,
            content_type=content_type,
            size_bytes=len(content),
            content_hash=content_hash,
            actor_user_id=filing_session.user_id,
        )
    except Exception:
        # DB persistence failed after a successful storage write. Clean up the
        # now-orphaned object rather than leaking stored file content with no
        # corresponding metadata record.
        storage.delete(storage_key)
        raise

    return document, False


def get_document(db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID) -> TaxDocument:
    """Raises DocumentNotFoundError if the document doesn't exist, doesn't
    belong to this filing session, or has been deleted."""
    document = tax_document_repo.get_document(db, filing_session_id, document_id)
    if document is None or document.status == DocumentStatus.DELETED:
        raise DocumentNotFoundError(document_id, filing_session_id)
    return document


def list_documents(db: Session, filing_session_id: uuid.UUID) -> list[TaxDocument]:
    _get_filing_session_or_raise(db, filing_session_id)
    return tax_document_repo.list_documents(db, filing_session_id)


def get_document_content(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID, *, storage: StorageProvider | None = None
) -> tuple[bytes, str, str]:
    """Returns (content, content_type, original_filename)."""
    document = get_document(db, filing_session_id, document_id)
    storage = storage or get_storage_provider()
    try:
        content = storage.read(document.storage_key)
    except StorageObjectNotFoundError as exc:
        raise StorageObjectMissingError(document.id) from exc
    return content, document.content_type, document.original_filename


def delete_document(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID, *, storage: StorageProvider | None = None
) -> TaxDocument:
    """Idempotent: deleting an already-deleted document is a safe no-op."""
    document = tax_document_repo.get_document(db, filing_session_id, document_id)
    if document is None:
        raise DocumentNotFoundError(document_id, filing_session_id)
    if document.status == DocumentStatus.DELETED:
        return document

    filing_session = _get_filing_session_or_raise(db, filing_session_id)
    storage = storage or get_storage_provider()
    # Storage delete happens before the DB flip so the DB never claims
    # "deleted" for a file that's actually still sitting in storage.
    storage.delete(document.storage_key)
    return tax_document_repo.mark_deleted(db, document, actor_user_id=filing_session.user_id)
