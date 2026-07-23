import uuid

from sqlalchemy.orm import Session

from app.engines.extraction.errors import DocumentProcessingJobNotFoundError, NoExtractionAvailableError
from app.integrations.ocr.base import ExtractionProvider
from app.integrations.ocr.provider import get_extraction_provider
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.provider import get_storage_provider
from app.models.document_extraction import DocumentExtraction
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import DocumentProcessingJobStatus, ExtractionProviderName
from app.models.extracted_field import ExtractedField
from app.repositories import document_processing as document_processing_repo
from app.services import consent as consent_service
from app.services import document as document_service
from app.services.questionnaire import get_filing_session_or_raise
from app.workers.document_extraction_worker import run_extraction_job


def start_extraction(
    db: Session,
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    provider: ExtractionProvider | None = None,
    storage: StorageProvider | None = None,
) -> DocumentProcessingJob:
    """Idempotent: if a COMPLETED job already exists for this document, it is
    returned as-is — no new job, no re-invoking the provider — matching this
    codebase's established safe-retry philosophy. A prior FAILED job does not
    block a fresh attempt (retry creates a new job).

    Ownership is enforced by routing through document_service.get_document,
    which is scoped by (filing_session_id, document_id) — the same chain used
    for every other document operation, not a document id looked up alone.
    """
    tax_document = document_service.get_document(db, filing_session_id, document_id)
    # Phase 10 exit criterion: consent must be recorded before document
    # upload/processing proceeds. Upload is already gated (app/services/
    # document.py); this repeats the check here so processing itself can
    # never proceed without it either, even for a document uploaded earlier
    # under consent that has since been withdrawn.
    consent_service.assert_required_consents_accepted(db, filing_session_id)

    existing = document_processing_repo.get_latest_job_for_document(db, tax_document.id)
    if existing is not None and existing.status == DocumentProcessingJobStatus.COMPLETED:
        return existing

    filing_session = get_filing_session_or_raise(db, filing_session_id)
    job = document_processing_repo.create_job(
        db,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=filing_session_id,
        actor_user_id=filing_session.user_id,
    )

    provider = provider or get_extraction_provider()
    storage = storage or get_storage_provider()
    job, _extraction = run_extraction_job(db, job, tax_document, provider=provider, storage=storage)
    return job


def get_job(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID, job_id: uuid.UUID
) -> DocumentProcessingJob:
    tax_document = document_service.get_document(db, filing_session_id, document_id)
    job = document_processing_repo.get_job(db, tax_document.id, job_id)
    if job is None:
        raise DocumentProcessingJobNotFoundError(job_id)
    return job


def get_latest_extraction(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID
) -> tuple[DocumentExtraction, list[ExtractedField]]:
    tax_document = document_service.get_document(db, filing_session_id, document_id)
    extraction = document_processing_repo.get_latest_extraction_for_document(db, tax_document.id)
    if extraction is None:
        raise NoExtractionAvailableError(tax_document.id)
    fields = document_processing_repo.list_fields_for_extraction(db, extraction.id)
    return extraction, fields
