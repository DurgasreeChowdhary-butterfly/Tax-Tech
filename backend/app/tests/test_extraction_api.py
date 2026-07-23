import io

import pytest

from app.integrations.ocr.base import ExtractionFailedError
from app.integrations.ocr.provider import get_extraction_provider
from app.main import app
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.tests.conftest import auth_headers

PDF_BYTES = b"%PDF-1.4\n%mock form16 for api extraction tests\n"


@pytest.fixture()
def uploaded_document_id(client, db_session):
    user = create_user(db_session, UserCreate(email="extraction-api@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    client.headers.update(auth_headers(user.id))
    upload_resp = client.post(
        f"/api/v1/filing-sessions/{session.id}/documents",
        files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    document_id = upload_resp.json()["document"]["id"]
    return session.id, document_id


def test_extraction_workflow_via_api(client, uploaded_document_id):
    filing_session_id, document_id = uploaded_document_id
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents/{document_id}/extraction"

    start_resp = client.post(base)
    assert start_resp.status_code == 200
    job = start_resp.json()
    assert job["status"] == "COMPLETED"

    job_resp = client.get(f"{base}/jobs/{job['id']}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "COMPLETED"

    extraction_resp = client.get(base)
    assert extraction_resp.status_code == 200
    body = extraction_resp.json()
    assert body["provider"] == "MOCK"
    field_names = {f["field_name"] for f in body["fields"]}
    assert field_names == {"employer_name", "pan", "gross_salary", "tds_deducted"}


def test_extraction_status_before_start_is_404(client, uploaded_document_id):
    filing_session_id, document_id = uploaded_document_id
    resp = client.get(f"/api/v1/filing-sessions/{filing_session_id}/documents/{document_id}/extraction")
    assert resp.status_code == 404


def test_extraction_failure_is_reported_not_500(client, uploaded_document_id):
    filing_session_id, document_id = uploaded_document_id
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents/{document_id}/extraction"

    class FailingProvider:
        def extract(self, content, content_type):
            raise ExtractionFailedError("simulated provider outage")

    app.dependency_overrides[get_extraction_provider] = lambda: FailingProvider()
    try:
        resp = client.post(base)
    finally:
        del app.dependency_overrides[get_extraction_provider]

    assert resp.status_code == 200  # the job failed; the HTTP call itself succeeded
    body = resp.json()
    assert body["status"] == "FAILED"
    # Security regression guard: the raw exception text must never reach the
    # API response — only a fixed, safe error_code/error_message may.
    assert body["error_code"] == "PROVIDER_ERROR"
    assert body["error_message"] == "The extraction provider failed to process the document."
    assert "simulated provider outage" not in str(body)


def test_storage_object_missing_does_not_leak_storage_key_via_api(client, document_storage, db_session, uploaded_document_id):
    import uuid

    filing_session_id, document_id = uploaded_document_id
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents/{document_id}/extraction"

    from app.repositories.tax_document import get_document as get_tax_document_row

    tax_document = get_tax_document_row(db_session, filing_session_id, uuid.UUID(document_id))
    document_storage.delete(tax_document.storage_key)  # simulate the file vanishing from storage

    resp = client.post(base)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "STORAGE_OBJECT_MISSING"
    serialized = str(body)
    assert tax_document.storage_key not in serialized
    assert str(filing_session_id) not in serialized
    assert "no storage object for key" not in serialized


def test_sensitive_exception_content_is_never_persisted_not_just_unexposed(client, db_session, uploaded_document_id):
    """Diagnostic-data audit regression: even though error_detail is never
    serialized by any API schema, it must also never be *persisted* with raw,
    unbounded exception content. Simulate a provider exception whose message
    embeds a storage key, PAN, a provider secret, a financial value, and
    document content, then inspect the DB row directly (not just the API
    response) to prove none of it reached error_detail."""
    import uuid

    filing_session_id, document_id = uploaded_document_id
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents/{document_id}/extraction"

    sensitive_payload = (
        "storage_key=filing-sessions/33333333-3333-3333-3333-333333333333/doc "
        "pan=ZZZPZ0000Z "
        "api_key=sk-test-provider-secret-999 "
        "tds_deducted=95000.00 "
        "raw_text='Form 16 for Jane Roe, PAN ZZZPZ0000Z'"
    )

    class FailingProvider:
        def extract(self, content, content_type):
            raise ExtractionFailedError(sensitive_payload)

    app.dependency_overrides[get_extraction_provider] = lambda: FailingProvider()
    try:
        resp = client.post(base)
    finally:
        del app.dependency_overrides[get_extraction_provider]

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "PROVIDER_ERROR"

    from app.repositories.document_processing import get_latest_job_for_document

    job = get_latest_job_for_document(db_session, uuid.UUID(document_id))
    assert job.error_detail == "ExtractionFailedError"
    for leaked_fragment in (
        "33333333-3333-3333-3333-333333333333",
        "ZZZPZ0000Z",
        "sk-test-provider-secret-999",
        "95000.00",
        "Jane Roe",
        "filing-sessions/",
    ):
        assert leaked_fragment not in job.error_detail


def test_cross_session_extraction_access_rejected_via_api(client, db_session, uploaded_document_id):
    filing_session_id, document_id = uploaded_document_id

    other_user = create_user(db_session, UserCreate(email="other-extraction-api@example.com", password="TestPassword123!"))
    other_session = create_filing_session(
        db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27")
    )

    other_base = f"/api/v1/filing-sessions/{other_session.id}/documents/{document_id}/extraction"
    assert client.post(other_base).status_code == 404
    assert client.get(other_base).status_code == 404


def test_unknown_document_returns_404(client, uploaded_document_id):
    import uuid

    filing_session_id, _document_id = uploaded_document_id
    resp = client.post(f"/api/v1/filing-sessions/{filing_session_id}/documents/{uuid.uuid4()}/extraction")
    assert resp.status_code == 404
