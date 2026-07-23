import uuid

from sqlalchemy.orm import Session

from app.models.consent_definition import ConsentDefinition
from app.models.enums import UserConsentStatus
from app.models.user_consent import UserConsent
from app.repositories import consent as consent_repo
from app.services.consent_errors import (
    ConsentDefinitionNotFoundError,
    MissingRequiredConsentError,
    NoActiveConsentToWithdrawError,
)
from app.services.questionnaire import get_filing_session_or_raise


def _get_owned_filing_session(db: Session, filing_session_id: uuid.UUID):
    """Loads the filing session. user_id is always derived from it
    server-side, never accepted as a separate client-supplied input (mirrors
    every other Phase 5-9 filing-session-scoped endpoint) — so a client can
    never pass a mismatched (user, filing_session) pair to begin with.
    Consent rows themselves are always looked up scoped by
    (user_id, filing_session_id, consent_definition_id) together (see
    app/repositories/consent.py), so a consent recorded under one filing
    session is structurally invisible/inaccessible through any other filing
    session — including a different session belonging to the SAME user.
    """
    return get_filing_session_or_raise(db, filing_session_id)


def get_required_consent_definitions(db: Session) -> list[ConsentDefinition]:
    """Backend-derived: the latest PUBLISHED version per required consent
    code. Never accepts a client-supplied version."""
    return [d for d in consent_repo.list_latest_published_definitions(db) if d.is_required]


def get_consent_status(db: Session, filing_session_id: uuid.UUID) -> list[UserConsent]:
    filing_session = _get_owned_filing_session(db, filing_session_id)
    return consent_repo.get_current_user_consents_for_session(
        db, user_id=filing_session.user_id, filing_session_id=filing_session.id
    )


def list_consent_overview(db: Session, filing_session_id: uuid.UUID) -> list[tuple[ConsentDefinition, UserConsent | None]]:
    """Every latest-published consent definition paired with this filing
    session's current acceptance status (None if never acted on) — the
    client-independent view a UI needs to know what to prompt for and what's
    already been accepted."""
    filing_session = _get_owned_filing_session(db, filing_session_id)
    definitions = consent_repo.list_latest_published_definitions(db)
    current_by_definition_id = {
        row.consent_definition_id: row
        for row in consent_repo.get_current_user_consents_for_session(
            db, user_id=filing_session.user_id, filing_session_id=filing_session.id
        )
    }
    return [(d, current_by_definition_id.get(d.id)) for d in definitions]


def _resolve_definition_for_code(db: Session, code: str) -> ConsentDefinition:
    definition = consent_repo.get_latest_published_by_code(db, code)
    if definition is None:
        raise ConsentDefinitionNotFoundError(code)
    return definition


def accept_consent(db: Session, filing_session_id: uuid.UUID, code: str) -> UserConsent:
    filing_session = _get_owned_filing_session(db, filing_session_id)
    definition = _resolve_definition_for_code(db, code)
    row, _created = consent_repo.accept(
        db,
        user_id=filing_session.user_id,
        filing_session_id=filing_session.id,
        consent_definition=definition,
        consent_code_for_audit=code,
    )
    return row


def withdraw_consent(db: Session, filing_session_id: uuid.UUID, code: str) -> UserConsent:
    filing_session = _get_owned_filing_session(db, filing_session_id)
    definition = _resolve_definition_for_code(db, code)
    current = consent_repo.get_current_user_consent(
        db, user_id=filing_session.user_id, filing_session_id=filing_session.id, consent_definition_id=definition.id
    )
    if current is None:
        # Never accepted (or withdrawn already and no row at all) — nothing
        # to withdraw. An already-WITHDRAWN current row is NOT an error here;
        # consent_repo.withdraw treats that as an idempotent no-op.
        raise NoActiveConsentToWithdrawError(code)

    row, _created = consent_repo.withdraw(
        db,
        user_id=filing_session.user_id,
        filing_session_id=filing_session.id,
        consent_definition=definition,
        consent_code_for_audit=code,
        current=current,
    )
    return row


def assert_required_consents_accepted(db: Session, filing_session_id: uuid.UUID) -> None:
    """Gate for actions documented as requiring prior consent (e.g. document
    upload/processing — docs/IMPLEMENTATION_PLAN.md Phase 10 exit criterion).
    Raises MissingRequiredConsentError listing the still-unaccepted codes;
    never silently proceeds and never guesses consent."""
    filing_session = _get_owned_filing_session(db, filing_session_id)
    required = get_required_consent_definitions(db)
    if not required:
        return

    current_rows = consent_repo.get_current_user_consents_for_session(
        db, user_id=filing_session.user_id, filing_session_id=filing_session.id
    )
    accepted_definition_ids = {row.consent_definition_id for row in current_rows if row.status == UserConsentStatus.ACCEPTED}

    missing = [d.code for d in required if d.id not in accepted_definition_ids]
    if missing:
        raise MissingRequiredConsentError(missing)


# --- V1 seed content -------------------------------------------------------
# Mirrors app/engines/tax/rule_data.py's role for tax_rule_sets: the actual
# published V1 consent definitions, used by fixtures/tests and by the real
# deployment bootstrap. Not exposed via any API (no admin surface exists yet
# — matches the questionnaire_versions/tax_rule_sets pattern of Phase 3/8).

_V1_CONSENT_DEFINITIONS = (
    {
        "code": "DATA_PROCESSING",
        "title": "Processing your tax information",
        "body_text": (
            "We process the income and deduction details you provide to prepare your tax estimate. "
            "We do not file your return or share your data with third parties for marketing."
        ),
        "is_required": True,
    },
    {
        "code": "DOCUMENT_STORAGE_AND_PROCESSING",
        "title": "Storing and reading your uploaded documents",
        "body_text": (
            "Documents you upload (e.g. Form 16) are stored in private storage and read by our "
            "extraction process to help fill in your details. You review and confirm every value "
            "before it is used."
        ),
        "is_required": True,
    },
)


def seed_v1_consent_definitions(db: Session) -> list[ConsentDefinition]:
    """Creates and publishes version 1 of each V1 required consent
    definition, idempotently (a code with an existing PUBLISHED version is
    left alone — this never edits or republishes over existing history)."""
    results = []
    for spec in _V1_CONSENT_DEFINITIONS:
        existing = consent_repo.get_latest_published_by_code(db, spec["code"])
        if existing is not None:
            results.append(existing)
            continue
        definition = consent_repo.create_definition(db, version_number=1, **spec)
        results.append(consent_repo.publish_definition(db, definition))
    return results
