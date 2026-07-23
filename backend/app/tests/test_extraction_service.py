import uuid

import pytest
from sqlalchemy import select

from app.core.database import Base
from app.engines.extraction.errors import DocumentProcessingJobNotFoundError, NoExtractionAvailableError
from app.integrations.ocr.base import ExtractionFailedError
from app.models.enums import DocumentProcessingJobStatus
from app.services import extraction as extraction_service
from app.services.document_errors import DocumentNotFoundError

# Tables Phase 6 is allowed to write to. Everything else (including tables
# from earlier phases already populated by the fixture, and any future
# domain/income table) must be untouched by the extraction path.
# `audit_logs` is a deliberate Phase 10 addition (EXTRACTION_STARTED/
# COMPLETED/FAILED events) — it is not a domain/income table, so recording
# audit history here does not violate this test's "no domain writes" intent.
_EXTRACTION_OWNED_TABLES = {"document_processing_jobs", "document_extractions", "extracted_fields", "audit_logs"}


def _row_counts(db_session) -> dict[str, int]:
    counts = {}
    for table_name, table in Base.metadata.tables.items():
        counts[table_name] = len(list(db_session.execute(select(table))))
    return counts


def test_start_extraction_produces_completed_job_and_fields(db_session, uploaded_document, document_storage):
    filing_session, tax_document = uploaded_document

    job = extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)

    assert job.status == DocumentProcessingJobStatus.COMPLETED
    extraction, fields = extraction_service.get_latest_extraction(db_session, filing_session.id, tax_document.id)
    assert extraction.document_processing_job_id == job.id
    assert len(fields) == 4  # the mock provider's Form16-like field set
    assert all(0.0 <= f.confidence <= 1.0 for f in fields)


def test_extraction_never_writes_outside_its_own_tables(db_session, uploaded_document, document_storage):
    filing_session, tax_document = uploaded_document

    before = _row_counts(db_session)
    extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)
    after = _row_counts(db_session)

    changed_tables = {name for name in before if before[name] != after[name]}
    assert changed_tables and changed_tables.issubset(_EXTRACTION_OWNED_TABLES), (
        f"extraction touched unexpected tables: {changed_tables - _EXTRACTION_OWNED_TABLES}"
    )


def test_repeated_start_is_idempotent_when_already_completed(db_session, uploaded_document, document_storage):
    filing_session, tax_document = uploaded_document

    first = extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)
    second = extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)

    assert first.id == second.id  # no second job created
    extraction, _fields = extraction_service.get_latest_extraction(db_session, filing_session.id, tax_document.id)
    # only one extraction row exists for the (single) completed job
    assert extraction.document_processing_job_id == first.id


def test_retry_after_failure_creates_a_new_job(db_session, uploaded_document, document_storage):
    filing_session, tax_document = uploaded_document

    class FailingProvider:
        def extract(self, content, content_type):
            raise ExtractionFailedError("simulated failure")

    failed_job = extraction_service.start_extraction(
        db_session, filing_session.id, tax_document.id, provider=FailingProvider(), storage=document_storage
    )
    assert failed_job.status == DocumentProcessingJobStatus.FAILED

    retried_job = extraction_service.start_extraction(
        db_session, filing_session.id, tax_document.id, storage=document_storage
    )

    assert retried_job.id != failed_job.id
    assert retried_job.status == DocumentProcessingJobStatus.COMPLETED


def test_cross_session_access_is_rejected(db_session, uploaded_document, document_storage):
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate

    filing_session, tax_document = uploaded_document
    other_user = create_user(db_session, UserCreate(email="other-extraction@example.com", password="TestPassword123!"))
    other_session = create_filing_session(
        db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27")
    )

    with pytest.raises(DocumentNotFoundError):
        extraction_service.start_extraction(db_session, other_session.id, tax_document.id, storage=document_storage)

    job = extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)

    with pytest.raises(DocumentNotFoundError):
        extraction_service.get_job(db_session, other_session.id, tax_document.id, job.id)

    with pytest.raises(DocumentNotFoundError):
        extraction_service.get_latest_extraction(db_session, other_session.id, tax_document.id)


def test_no_extraction_available_before_any_job_runs(db_session, uploaded_document):
    filing_session, tax_document = uploaded_document

    with pytest.raises(NoExtractionAvailableError):
        extraction_service.get_latest_extraction(db_session, filing_session.id, tax_document.id)


def test_unknown_job_id_is_rejected(db_session, uploaded_document, document_storage):
    filing_session, tax_document = uploaded_document
    extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)

    with pytest.raises(DocumentProcessingJobNotFoundError):
        extraction_service.get_job(db_session, filing_session.id, tax_document.id, uuid.uuid4())
