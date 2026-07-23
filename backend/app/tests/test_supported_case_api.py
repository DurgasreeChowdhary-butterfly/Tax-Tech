import uuid

from app.models.enums import FilerCategory, ResidencyStatus
from app.repositories.filing_session import create_filing_session, update_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.user import UserCreate
from app.tests.conftest import auth_headers


def _make_session(db_session, client, *, email, **update_fields):
    user = create_user(db_session, UserCreate(email=email, password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    if update_fields:
        session = update_filing_session(db_session, session, FilingSessionUpdate(**update_fields))
    client.headers.update(auth_headers(user.id))
    return session


def test_get_supported_case_returns_result_via_api(client, db_session, published_tax_rule_set):
    session = _make_session(
        db_session, client, email="supported-case-api-1@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.OTHER,
    )

    resp = client.get(f"/api/v1/filing-sessions/{session.id}/supported-case")

    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "NOT_SUPPORTED"
    assert "FILER_CATEGORY_UNSUPPORTED" in body["reasons"]


def test_unknown_filing_session_returns_404(client, db_session):
    _make_session(db_session, client, email="supported-case-api-unknown@example.com")
    resp = client.get(f"/api/v1/filing-sessions/{uuid.uuid4()}/supported-case")
    assert resp.status_code == 404


def test_cross_session_isolation_via_api(client, db_session, published_tax_rule_set):
    session_a = _make_session(
        db_session, client, email="supported-case-api-a@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.OTHER,
    )
    # _make_session re-authenticates `client` as each session's own owner —
    # each GET below runs as the user who actually owns that session.
    body_a = client.get(f"/api/v1/filing-sessions/{session_a.id}/supported-case").json()

    session_b = _make_session(
        db_session, client, email="supported-case-api-b@example.com",
        residency_status=ResidencyStatus.NON_RESIDENT, filer_category=FilerCategory.SALARIED,
    )
    body_b = client.get(f"/api/v1/filing-sessions/{session_b.id}/supported-case").json()

    assert body_a["outcome"] == "NOT_SUPPORTED"
    assert "FILER_CATEGORY_UNSUPPORTED" in body_a["reasons"]
    assert "RESIDENCY_STATUS_UNSUPPORTED" not in body_a["reasons"]

    assert body_b["outcome"] == "NOT_SUPPORTED"
    assert "RESIDENCY_STATUS_UNSUPPORTED" in body_b["reasons"]
    assert "FILER_CATEGORY_UNSUPPORTED" not in body_b["reasons"]


def test_cross_user_token_cannot_read_another_users_session(client, db_session, published_tax_rule_set):
    session_a = _make_session(
        db_session, client, email="supported-case-api-owner@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.OTHER,
    )
    # Re-authenticate as a second, unrelated user — same client, different token.
    _make_session(db_session, client, email="supported-case-api-intruder@example.com")

    resp = client.get(f"/api/v1/filing-sessions/{session_a.id}/supported-case")
    assert resp.status_code == 404  # never 403 — existence is not confirmed either


def test_response_never_contains_raw_or_sensitive_values(client, db_session, published_tax_rule_set):
    """The response schema only exposes outcome + a fixed set of reason codes
    — never raw PAN, storage keys, exception text, or free-form diagnostics."""
    session = _make_session(
        db_session, client, email="supported-case-api-sensitive@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED,
    )

    resp = client.get(f"/api/v1/filing-sessions/{session.id}/supported-case")
    body = resp.json()

    assert set(body.keys()) == {"outcome", "reasons"}
    known_reason_prefixes = (
        "NO_PUBLISHED_RULE_SET", "FILER_CATEGORY_UNSUPPORTED", "RESIDENCY_STATUS_UNSUPPORTED",
        "UNSUPPORTED_SCENARIO:", "COMPLEXITY_NOT_SUPPORTED", "COMPLEXITY_REVIEW_REQUIRED",
        "REVIEW_REQUIRED_FLAG_ACTIVE", "FILER_CATEGORY_MISSING", "RESIDENCY_STATUS_MISSING", "NO_VERIFIED_INCOME",
    )
    for reason in body["reasons"]:
        assert reason.startswith(known_reason_prefixes)
