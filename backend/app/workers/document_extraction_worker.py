from app.engines.extraction.failure_classification import classify_failure, sanitize_diagnostic_detail
from app.engines.extraction.normalization import normalize_field_candidates
from app.integrations.ocr.base import ExtractionProvider
from app.integrations.storage.base import StorageProvider
from app.models.document_extraction import DocumentExtraction
from app.models.document_processing_job import DocumentProcessingJob
from app.models.tax_document import TaxDocument
from app.repositories import document_processing as document_processing_repo


def run_extraction_job(
    db,
    job: DocumentProcessingJob,
    tax_document: TaxDocument,
    *,
    provider: ExtractionProvider,
    storage: StorageProvider,
) -> tuple[DocumentProcessingJob, DocumentExtraction | None]:
    """Runs one processing job to completion (or failure) synchronously.

    Writes only to document_processing_jobs / document_extractions /
    extracted_fields — never to any domain income/deduction table (none of
    those are imported or referenced here). A provider/storage failure is an
    expected, handled outcome: the job is marked FAILED with a safe, fixed
    error_code plus a bounded, sanitized error_detail (exception class name
    only — never the exception message/content, which is unbounded and can
    embed storage keys, paths, secrets, PAN, or document content; see
    sanitize_diagnostic_detail). error_detail is for internal diagnostics
    only and is never serialized by any API schema. (job, None) is returned
    rather than raising, so callers can retry by starting a new job instead
    of the whole request blowing up.
    """
    document_processing_repo.mark_running(db, job)

    try:
        content = storage.read(tax_document.storage_key)
        result = provider.extract(content, tax_document.content_type)
    except Exception as exc:  # noqa: BLE001 - any provider/storage failure is a valid job outcome, not a crash
        code = classify_failure(exc)
        failed_job = document_processing_repo.mark_failed(
            db,
            job,
            error_code=code,
            error_detail=sanitize_diagnostic_detail(exc),
            filing_session_id=tax_document.filing_session_id,
        )
        return failed_job, None

    normalized_fields = normalize_field_candidates(result.fields)
    extraction = document_processing_repo.create_extraction_with_fields(
        db,
        document_processing_job_id=job.id,
        tax_document_id=tax_document.id,
        provider=job.provider,
        provider_version=result.provider_version,
        raw_output=result.raw_output,
        fields=normalized_fields,
    )
    completed_job = document_processing_repo.mark_completed(db, job, filing_session_id=tax_document.filing_session_id)
    return completed_job, extraction
