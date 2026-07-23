import io

import pytest

from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.tests.conftest import auth_headers

PDF_BYTES = b"%PDF-1.4\n%mock form16 for verification api tests\n"


@pytest.fixture()
def extracted_document_ids(client, db_session):
    user = create_user(db_session, UserCreate(email="verification-api@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    client.headers.update(auth_headers(user.id))
    upload_resp = client.post(
        f"/api/v1/filing-sessions/{session.id}/documents",
        files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    document_id = upload_resp.json()["document"]["id"]
    base = f"/api/v1/filing-sessions/{session.id}/documents/{document_id}/extraction"
    client.post(base)
    return session.id, document_id


def _field_id(client, session_id, document_id, field_name):
    review = client.get(f"/api/v1/filing-sessions/{session_id}/documents/{document_id}/extraction/review").json()
    return next(f["id"] for f in review if f["field_name"] == field_name)


def test_review_endpoint_lists_fields_with_support_and_verification_state(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    resp = client.get(f"/api/v1/filing-sessions/{session_id}/documents/{document_id}/extraction/review")
    assert resp.status_code == 200
    body = resp.json()

    by_name = {f["field_name"]: f for f in body}
    assert by_name["gross_salary"]["is_supported"] is True
    assert by_name["gross_salary"]["current_verification"] is None
    assert by_name["pan"]["is_supported"] is False


def test_confirm_field_via_api(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "gross_salary")
    base = f"/api/v1/filing-sessions/{session_id}/documents/{document_id}"

    resp = client.post(f"{base}/extraction/fields/{field_id}/verify", json={"action": "CONFIRM"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verification"]["action"] == "CONFIRM"
    assert body["salary_income"]["gross_salary"] == "1200000.00"


def test_correct_field_via_api(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "gross_salary")
    base = f"/api/v1/filing-sessions/{session_id}/documents/{document_id}"

    resp = client.post(
        f"{base}/extraction/fields/{field_id}/verify", json={"action": "CORRECT", "value": "1300000.00"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verification"]["action"] == "CORRECT"
    assert body["salary_income"]["gross_salary"] == "1300000.00"


def test_unsupported_field_via_api_returns_400(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "pan")
    base = f"/api/v1/filing-sessions/{session_id}/documents/{document_id}"

    resp = client.post(f"{base}/extraction/fields/{field_id}/verify", json={"action": "CONFIRM"})
    assert resp.status_code == 400


def test_invalid_value_via_api_returns_400(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "gross_salary")
    base = f"/api/v1/filing-sessions/{session_id}/documents/{document_id}"

    resp = client.post(
        f"{base}/extraction/fields/{field_id}/verify", json={"action": "CORRECT", "value": "-1.00"}
    )
    assert resp.status_code == 400


def test_cross_session_verify_rejected_via_api(client, db_session, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "gross_salary")

    other_user = create_user(db_session, UserCreate(email="other-verify-api@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))

    other_base = f"/api/v1/filing-sessions/{other_session.id}/documents/{document_id}"
    resp = client.post(f"{other_base}/extraction/fields/{field_id}/verify", json={"action": "CONFIRM"})
    assert resp.status_code == 404

    resp = client.get(f"{other_base}/extraction/review")
    assert resp.status_code == 404


def test_repeated_confirm_via_api_is_idempotent(client, extracted_document_ids):
    session_id, document_id = extracted_document_ids
    field_id = _field_id(client, session_id, document_id, "gross_salary")
    base = f"/api/v1/filing-sessions/{session_id}/documents/{document_id}"

    first = client.post(f"{base}/extraction/fields/{field_id}/verify", json={"action": "CONFIRM"})
    second = client.post(f"{base}/extraction/fields/{field_id}/verify", json={"action": "CONFIRM"})

    assert first.json()["verification"]["id"] == second.json()["verification"]["id"]
