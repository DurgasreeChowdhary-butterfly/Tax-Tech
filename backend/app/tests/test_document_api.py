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
    user = create_user(db_session, UserCreate(email="doc-api@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    client.headers.update(auth_headers(user.id))
    return session.id


def test_multipart_upload_status_content_flow(client, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"

    upload_resp = client.post(base, files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    assert upload_resp.status_code == 200
    body = upload_resp.json()
    assert body["is_duplicate"] is False
    document_id = body["document"]["id"]
    assert body["document"]["content_type"] == "application/pdf"
    assert body["document"]["status"] == "UPLOADED"

    status_resp = client.get(f"{base}/{document_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["id"] == document_id

    list_resp = client.get(base)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["documents"]) == 1

    content_resp = client.get(f"{base}/{document_id}/content")
    assert content_resp.status_code == 200
    assert content_resp.content == PDF_BYTES
    assert content_resp.headers["content-type"] == "application/pdf"

    delete_resp = client.delete(f"{base}/{document_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "DELETED"

    gone_resp = client.get(f"{base}/{document_id}")
    assert gone_resp.status_code == 404


def test_upload_rejects_spoofed_content_via_api(client, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"
    resp = client.post(base, files={"file": ("innocent.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")})
    assert resp.status_code == 400


def test_upload_rejects_empty_file_via_api(client, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"
    resp = client.post(base, files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")})
    assert resp.status_code == 400


def test_upload_path_traversal_filename_via_api(client, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"
    resp = client.post(base, files={"file": ("../../etc/passwd", io.BytesIO(PDF_BYTES), "application/pdf")})
    assert resp.status_code == 200
    document = resp.json()["document"]
    assert document["original_filename"] == "passwd"


def test_no_public_url_ever_appears_in_responses(client, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"
    resp = client.post(base, files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    body = resp.json()

    serialized = str(body)
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "storage_key" not in body["document"]  # internal pointer never exposed


def test_cross_session_document_access_rejected_via_api(client, db_session, filing_session_id):
    other_user = create_user(db_session, UserCreate(email="other-session@example.com", password="TestPassword123!"))
    other_session = create_filing_session(
        db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27")
    )

    base = f"/api/v1/filing-sessions/{filing_session_id}/documents"
    upload_resp = client.post(base, files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
    document_id = upload_resp.json()["document"]["id"]

    other_base = f"/api/v1/filing-sessions/{other_session.id}/documents"
    assert client.get(f"{other_base}/{document_id}").status_code == 404
    assert client.get(f"{other_base}/{document_id}/content").status_code == 404
    assert client.delete(f"{other_base}/{document_id}").status_code == 404


def test_unknown_filing_session_returns_404(client, filing_session_id):
    import uuid

    # filing_session_id fixture only run for its side effect of authenticating `client`.
    resp = client.post(
        f"/api/v1/filing-sessions/{uuid.uuid4()}/documents",
        files={"file": ("form16.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert resp.status_code == 404
