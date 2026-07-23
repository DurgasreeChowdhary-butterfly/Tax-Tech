import uuid

from app.models.enums import FilerCategory, ResidencyStatus, VerificationAction
from app.repositories.filing_session import create_filing_session, update_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.user import UserCreate
from app.services import verification as verification_service
from app.tests.conftest import auth_headers


def _supported_session(db_session, client, extracted_document, gross_salary="1000000.00", tds="50000.00"):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["gross_salary"].id,
        action=VerificationAction.CORRECT, value=gross_salary,
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["tds_deducted"].id,
        action=VerificationAction.CORRECT, value=tds,
    )
    client.headers.update(auth_headers(filing_session.user_id))
    return filing_session


def test_get_calculation_via_api(client, db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _supported_session(db_session, client, extracted_document)

    resp = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW")
    assert resp.status_code == 200
    body = resp.json()
    assert body["calculation"]["regime"] == "NEW"
    assert body["calculation"]["gross_total_income"] == "925000.00"
    assert body["calculation"]["total_tax_liability"] == "0.00" or body["calculation"]["total_tax_liability"] == "0"
    assert len(body["line_items"]) > 0
    assert body["line_items"][0]["sequence_index"] == 1


def test_incomplete_case_returns_409(client, db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session, *_ = extracted_document
    client.headers.update(auth_headers(filing_session.user_id))
    resp = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW")
    assert resp.status_code == 409


def test_unknown_filing_session_returns_404(client, db_session):
    user = create_user(db_session, UserCreate(email="calc-api-unknown@example.com", password="TestPassword123!"))
    client.headers.update(auth_headers(user.id))
    resp = client.get(f"/api/v1/filing-sessions/{uuid.uuid4()}/calculations/NEW")
    assert resp.status_code == 404


def test_cross_user_access_to_anothers_session_is_rejected(client, db_session, extracted_document, real_fy2025_26_rule_set):
    """Phase 11: a different user's valid token must not be able to reach
    another user's filing session at all — rejected at the ownership
    dependency, before the calculation/supported-case logic ever runs."""
    filing_session = _supported_session(db_session, client, extracted_document)
    client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW")

    other_user = create_user(db_session, UserCreate(email="calc-api-cross@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))

    # Still authenticated as the FIRST session's owner — not other_session's owner.
    resp = client.get(f"/api/v1/filing-sessions/{other_session.id}/calculations/NEW")
    assert resp.status_code == 404
    body = resp.json()
    assert "925000" not in str(body)  # no leakage of the first session's figures


def test_different_sessions_yield_independent_results_no_leakage(client, db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _supported_session(db_session, client, extracted_document)
    first_body = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW").json()
    assert first_body["calculation"]["gross_total_income"] == "925000.00"

    other_user = create_user(db_session, UserCreate(email="calc-api-cross-owner@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))
    client.headers.update(auth_headers(other_user.id))  # re-authenticate as the actual owner

    resp = client.get(f"/api/v1/filing-sessions/{other_session.id}/calculations/NEW")
    assert resp.status_code == 409  # INCOMPLETE for the other (empty) session, not the first session's result
    body = resp.json()
    assert "925000" not in str(body)  # no leakage of the first session's figures


def test_repeated_get_is_idempotent_via_api(client, db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _supported_session(db_session, client, extracted_document)

    first = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW").json()
    second = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW").json()
    assert first["calculation"]["id"] == second["calculation"]["id"]


def test_response_contains_no_sensitive_diagnostics(client, db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _supported_session(db_session, client, extracted_document)
    resp = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW")
    body_text = resp.text
    assert "input_fingerprint" not in body_text  # internal-only, never serialized
    assert str(filing_session.user_id) not in body_text
