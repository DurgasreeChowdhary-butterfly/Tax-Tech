import io

import pytest

from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.tests.conftest import auth_headers

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n"


@pytest.fixture()
def filing_session_id(db_session, client):
    user = create_user(db_session, UserCreate(email="consent-api@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    client.headers.update(auth_headers(user.id))
    return session.id


def test_consent_status_lists_required_definitions_as_unaccepted(client, filing_session_id, consent_definitions_v1):
    resp = client.get(f"/api/v1/filing-sessions/{filing_session_id}/consents")
    assert resp.status_code == 200
    body = resp.json()
    assert {row["code"] for row in body} == {"DATA_PROCESSING", "DOCUMENT_STORAGE_AND_PROCESSING"}
    assert all(row["status"] is None for row in body)
    assert all(row["is_required"] for row in body)


def test_accept_then_withdraw_via_api(client, filing_session_id, consent_definitions_v1):
    base = f"/api/v1/filing-sessions/{filing_session_id}/consents"

    accept_resp = client.post(f"{base}/DATA_PROCESSING/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    status_resp = client.get(base)
    data_processing = next(row for row in status_resp.json() if row["code"] == "DATA_PROCESSING")
    assert data_processing["status"] == "ACCEPTED"

    withdraw_resp = client.post(f"{base}/DATA_PROCESSING/withdraw")
    assert withdraw_resp.status_code == 200
    assert withdraw_resp.json()["status"] == "WITHDRAWN"


def test_document_upload_is_rejected_without_required_consent(client, filing_session_id, consent_definitions_v1):
    upload_resp = client.post(
        f"/api/v1/filing-sessions/{filing_session_id}/documents",
        files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert upload_resp.status_code == 403


def test_document_upload_succeeds_after_required_consent_accepted(client, filing_session_id, consent_definitions_v1):
    base = f"/api/v1/filing-sessions/{filing_session_id}/consents"
    client.post(f"{base}/DATA_PROCESSING/accept")
    client.post(f"{base}/DOCUMENT_STORAGE_AND_PROCESSING/accept")

    upload_resp = client.post(
        f"/api/v1/filing-sessions/{filing_session_id}/documents",
        files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert upload_resp.status_code == 200


def test_withdraw_unknown_consent_is_not_found(client, filing_session_id, consent_definitions_v1):
    resp = client.post(f"/api/v1/filing-sessions/{filing_session_id}/consents/DATA_PROCESSING/withdraw")
    assert resp.status_code == 404
