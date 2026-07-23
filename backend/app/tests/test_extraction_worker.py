from app.integrations.ocr.base import ExtractionFailedError, ExtractionResult, FieldCandidate
from app.models.enums import DocumentProcessingJobStatus, ExtractionFailureCode, ExtractionProviderName
from app.repositories import document_processing as document_processing_repo
from app.workers.document_extraction_worker import run_extraction_job


class _FakeProvider:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def extract(self, content, content_type):
        if self._error:
            raise self._error
        return self._result


def test_worker_success_path_persists_extraction_and_fields(db_session, uploaded_document, document_storage):
    _filing_session, tax_document = uploaded_document
    job = document_processing_repo.create_job(
        db_session,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=_filing_session.id,
        actor_user_id=_filing_session.user_id,
    )

    fake_result = ExtractionResult(
        provider_version="fake-v1",
        raw_output={"fields": [{"field_name": "a", "value": "b", "confidence": 0.7}]},
        fields=[FieldCandidate(field_name="a", value="b", confidence=0.7)],
    )
    provider = _FakeProvider(result=fake_result)

    completed_job, extraction = run_extraction_job(
        db_session, job, tax_document, provider=provider, storage=document_storage
    )

    assert completed_job.status == DocumentProcessingJobStatus.COMPLETED
    assert extraction is not None
    fields = document_processing_repo.list_fields_for_extraction(db_session, extraction.id)
    assert len(fields) == 1
    assert fields[0].field_name == "a"
    assert fields[0].confidence == 0.7


def test_worker_provider_failure_marks_job_failed_and_creates_no_extraction(db_session, uploaded_document, document_storage):
    _filing_session, tax_document = uploaded_document
    job = document_processing_repo.create_job(
        db_session,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=_filing_session.id,
        actor_user_id=_filing_session.user_id,
    )

    provider = _FakeProvider(error=ExtractionFailedError("provider blew up"))

    failed_job, extraction = run_extraction_job(
        db_session, job, tax_document, provider=provider, storage=document_storage
    )

    assert failed_job.status == DocumentProcessingJobStatus.FAILED
    assert failed_job.error_code == ExtractionFailureCode.PROVIDER_ERROR
    # error_detail is bounded/sanitized to the exception class name only —
    # the raw message ("provider blew up") must never be persisted.
    assert failed_job.error_detail == "ExtractionFailedError"
    assert "provider blew up" not in failed_job.error_detail
    assert extraction is None
    assert document_processing_repo.get_extraction_for_job(db_session, job.id) is None


def test_worker_missing_storage_object_marks_job_failed(db_session, uploaded_document, document_storage):
    _filing_session, tax_document = uploaded_document
    job = document_processing_repo.create_job(
        db_session,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=_filing_session.id,
        actor_user_id=_filing_session.user_id,
    )

    # Simulate the backing file vanishing before extraction runs.
    document_storage.delete(tax_document.storage_key)

    from app.integrations.ocr.mock_provider import MockFormExtractionProvider

    failed_job, extraction = run_extraction_job(
        db_session, job, tax_document, provider=MockFormExtractionProvider(), storage=document_storage
    )

    assert failed_job.status == DocumentProcessingJobStatus.FAILED
    assert failed_job.error_code == ExtractionFailureCode.STORAGE_OBJECT_MISSING
    # error_detail must be bounded/sanitized (class name only) — the storage
    # key must never be persisted, even internally (docs/DATA_MODEL.md
    # Sensitive-data notes: DB stores pointers, not raw internal detail).
    assert failed_job.error_detail == "StorageObjectNotFoundError"
    assert tax_document.storage_key not in failed_job.error_detail
    assert extraction is None


def test_sensitive_values_embedded_in_exception_message_are_never_persisted(
    db_session, uploaded_document, document_storage
):
    """Regression test for the Phase 6/7 diagnostic-data audit: a provider
    exception message can legitimately embed anything (storage keys, PAN,
    provider secrets, financial values, document content) — none of that may
    ever reach error_detail, which must be bounded to the exception class
    name only."""
    _filing_session, tax_document = uploaded_document
    job = document_processing_repo.create_job(
        db_session,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=_filing_session.id,
        actor_user_id=_filing_session.user_id,
    )

    sensitive_payload = (
        "storage_key=filing-sessions/11111111-1111-1111-1111-111111111111/"
        "22222222-2222-2222-2222-222222222222 "
        "pan=ABCPD1234E "
        "provider_token=sk-live-supersecretprovidertoken123 "
        "gross_salary=1234567.89 "
        "document_text='Employee Name: John Doe, Basic Salary: 500000'"
    )
    provider = _FakeProvider(error=ExtractionFailedError(sensitive_payload))

    failed_job, extraction = run_extraction_job(
        db_session, job, tax_document, provider=provider, storage=document_storage
    )

    assert failed_job.status == DocumentProcessingJobStatus.FAILED
    assert failed_job.error_code == ExtractionFailureCode.PROVIDER_ERROR
    assert failed_job.error_detail == "ExtractionFailedError"
    for leaked_fragment in (
        "11111111-1111-1111-1111-111111111111",
        "ABCPD1234E",
        "sk-live-supersecretprovidertoken123",
        "1234567.89",
        "John Doe",
        "500000",
        "filing-sessions/",
    ):
        assert leaked_fragment not in failed_job.error_detail
    assert extraction is None
