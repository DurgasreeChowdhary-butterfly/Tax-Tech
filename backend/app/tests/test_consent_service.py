import pytest

from app.models.enums import UserConsentStatus
from app.repositories import consent as consent_repo
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.services import consent as consent_service
from app.services.consent_errors import (
    ConsentDefinitionNotFoundError,
    MissingRequiredConsentError,
    NoActiveConsentToWithdrawError,
)


@pytest.fixture()
def filing_session(db_session):
    user = create_user(db_session, UserCreate(email="consent-user@example.com", password="TestPassword123!"))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def test_seed_publishes_required_v1_definitions(db_session, consent_definitions_v1):
    codes = {d.code for d in consent_definitions_v1}
    assert codes == {"DATA_PROCESSING", "DOCUMENT_STORAGE_AND_PROCESSING"}
    assert all(d.is_required for d in consent_definitions_v1)
    assert all(d.status.value == "PUBLISHED" for d in consent_definitions_v1)


def test_required_resolution_is_backend_derived_to_latest_published_version(db_session, consent_definitions_v1):
    """Publishing a v2 of one code must make required-consent resolution
    return v2, not v1 — the resolution is never pinned to a client-supplied
    version."""
    v2_draft = consent_repo.create_definition(
        db_session, code="DATA_PROCESSING", version_number=2, title="Reworded", body_text="v2 text", is_required=True
    )
    consent_repo.publish_definition(db_session, v2_draft)

    required = consent_service.get_required_consent_definitions(db_session)
    data_processing = next(d for d in required if d.code == "DATA_PROCESSING")
    assert data_processing.version_number == 2


def test_accept_records_exact_accepted_version(db_session, consent_definitions_v1, filing_session):
    definition = consent_definitions_v1[0]
    row = consent_service.accept_consent(db_session, filing_session.id, definition.code)

    assert row.status == UserConsentStatus.ACCEPTED
    assert row.consent_definition_id == definition.id
    assert row.is_current is True


def test_accept_is_idempotent_on_exact_retry(db_session, consent_definitions_v1, filing_session):
    definition = consent_definitions_v1[0]
    first = consent_service.accept_consent(db_session, filing_session.id, definition.code)
    second = consent_service.accept_consent(db_session, filing_session.id, definition.code)

    assert first.id == second.id
    history = consent_repo.get_user_consent_history(
        db_session, user_id=filing_session.user_id, filing_session_id=filing_session.id, consent_definition_id=definition.id
    )
    assert len(history) == 1


def test_withdraw_without_prior_acceptance_is_rejected(db_session, consent_definitions_v1, filing_session):
    definition = consent_definitions_v1[0]
    with pytest.raises(NoActiveConsentToWithdrawError):
        consent_service.withdraw_consent(db_session, filing_session.id, definition.code)


def test_withdrawal_is_historical_and_reacceptance_creates_new_row(db_session, consent_definitions_v1, filing_session):
    definition = consent_definitions_v1[0]

    accepted = consent_service.accept_consent(db_session, filing_session.id, definition.code)
    withdrawn = consent_service.withdraw_consent(db_session, filing_session.id, definition.code)
    reaccepted = consent_service.accept_consent(db_session, filing_session.id, definition.code)

    assert withdrawn.status == UserConsentStatus.WITHDRAWN
    assert withdrawn.supersedes_id == accepted.id
    assert reaccepted.status == UserConsentStatus.ACCEPTED
    assert reaccepted.id != accepted.id  # never resurrects the original row
    assert reaccepted.supersedes_id == withdrawn.id

    history = consent_repo.get_user_consent_history(
        db_session, user_id=filing_session.user_id, filing_session_id=filing_session.id, consent_definition_id=definition.id
    )
    assert [row.status for row in history] == [
        UserConsentStatus.ACCEPTED,
        UserConsentStatus.WITHDRAWN,
        UserConsentStatus.ACCEPTED,
    ]
    assert history[0].id == accepted.id
    assert history[-1].id == reaccepted.id


def test_withdraw_is_idempotent_on_repeat(db_session, consent_definitions_v1, filing_session):
    definition = consent_definitions_v1[0]
    consent_service.accept_consent(db_session, filing_session.id, definition.code)
    first_withdraw = consent_service.withdraw_consent(db_session, filing_session.id, definition.code)
    second_withdraw = consent_service.withdraw_consent(db_session, filing_session.id, definition.code)

    assert first_withdraw.id == second_withdraw.id
    history = consent_repo.get_user_consent_history(
        db_session, user_id=filing_session.user_id, filing_session_id=filing_session.id, consent_definition_id=definition.id
    )
    assert len(history) == 2  # ACCEPTED, WITHDRAWN — no duplicate WITHDRAWN


def test_unknown_consent_code_is_rejected(db_session, consent_definitions_v1, filing_session):
    with pytest.raises(ConsentDefinitionNotFoundError):
        consent_service.accept_consent(db_session, filing_session.id, "NOT_A_REAL_CODE")


def test_required_consent_gate_blocks_until_all_accepted(db_session, consent_definitions_v1, filing_session):
    with pytest.raises(MissingRequiredConsentError) as excinfo:
        consent_service.assert_required_consents_accepted(db_session, filing_session.id)
    assert set(excinfo.value.missing_codes) == {"DATA_PROCESSING", "DOCUMENT_STORAGE_AND_PROCESSING"}

    consent_service.accept_consent(db_session, filing_session.id, "DATA_PROCESSING")
    with pytest.raises(MissingRequiredConsentError) as excinfo:
        consent_service.assert_required_consents_accepted(db_session, filing_session.id)
    assert excinfo.value.missing_codes == ["DOCUMENT_STORAGE_AND_PROCESSING"]

    consent_service.accept_consent(db_session, filing_session.id, "DOCUMENT_STORAGE_AND_PROCESSING")
    consent_service.assert_required_consents_accepted(db_session, filing_session.id)  # no longer raises


def test_consent_is_isolated_per_filing_session_even_for_the_same_user(db_session, consent_definitions_v1):
    """Accepting consent under one filing session must NOT satisfy the
    required-consent gate for a different filing session — even one
    belonging to the same user (cross-session isolation)."""
    user = create_user(db_session, UserCreate(email="two-sessions@example.com", password="TestPassword123!"))
    session_a = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2025-26"))
    session_b = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    for definition in consent_definitions_v1:
        consent_service.accept_consent(db_session, session_a.id, definition.code)

    consent_service.assert_required_consents_accepted(db_session, session_a.id)  # fine
    with pytest.raises(MissingRequiredConsentError):
        consent_service.assert_required_consents_accepted(db_session, session_b.id)  # session_b never consented

    status_a = consent_service.get_consent_status(db_session, session_a.id)
    status_b = consent_service.get_consent_status(db_session, session_b.id)
    assert len(status_a) == 2
    assert len(status_b) == 0
