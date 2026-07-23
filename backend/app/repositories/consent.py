import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.consent_definition import ConsentDefinition
from app.models.enums import ActorType, AuditEventCode, ConsentDefinitionStatus, UserConsentStatus
from app.models.user_consent import UserConsent


def create_definition(
    db: Session, *, code: str, version_number: int, title: str, body_text: str, is_required: bool
) -> ConsentDefinition:
    definition = ConsentDefinition(
        code=code, version_number=version_number, title=title, body_text=body_text, is_required=is_required
    )
    db.add(definition)
    db.commit()
    db.refresh(definition)
    return definition


def publish_definition(db: Session, definition: ConsentDefinition) -> ConsentDefinition:
    definition.status = ConsentDefinitionStatus.PUBLISHED
    definition.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(definition)
    return definition


def get_definition_by_id(db: Session, consent_definition_id: uuid.UUID) -> ConsentDefinition | None:
    return db.get(ConsentDefinition, consent_definition_id)


def get_latest_published_by_code(db: Session, code: str) -> ConsentDefinition | None:
    stmt = (
        select(ConsentDefinition)
        .where(ConsentDefinition.code == code, ConsentDefinition.status == ConsentDefinitionStatus.PUBLISHED)
        .order_by(ConsentDefinition.version_number.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def list_latest_published_definitions(db: Session) -> list[ConsentDefinition]:
    """One row per `code`: its highest-version_number PUBLISHED row. Backend-
    derived — never trusts a client-supplied version."""
    stmt = (
        select(ConsentDefinition)
        .where(ConsentDefinition.status == ConsentDefinitionStatus.PUBLISHED)
        .order_by(ConsentDefinition.code, ConsentDefinition.version_number.desc())
    )
    latest_by_code: dict[str, ConsentDefinition] = {}
    for definition in db.execute(stmt).scalars().all():
        if definition.code not in latest_by_code:
            latest_by_code[definition.code] = definition
    return list(latest_by_code.values())


def get_current_user_consent(
    db: Session, *, user_id: uuid.UUID, filing_session_id: uuid.UUID, consent_definition_id: uuid.UUID
) -> UserConsent | None:
    stmt = select(UserConsent).where(
        UserConsent.user_id == user_id,
        UserConsent.filing_session_id == filing_session_id,
        UserConsent.consent_definition_id == consent_definition_id,
        UserConsent.is_current.is_(True),
    )
    return db.execute(stmt).scalars().first()


def get_current_user_consents_for_session(db: Session, *, user_id: uuid.UUID, filing_session_id: uuid.UUID) -> list[UserConsent]:
    stmt = select(UserConsent).where(
        UserConsent.user_id == user_id,
        UserConsent.filing_session_id == filing_session_id,
        UserConsent.is_current.is_(True),
    )
    return list(db.execute(stmt).scalars().all())


def get_user_consent_history(
    db: Session, *, user_id: uuid.UUID, filing_session_id: uuid.UUID, consent_definition_id: uuid.UUID
) -> list[UserConsent]:
    stmt = (
        select(UserConsent)
        .where(
            UserConsent.user_id == user_id,
            UserConsent.filing_session_id == filing_session_id,
            UserConsent.consent_definition_id == consent_definition_id,
        )
        .order_by(UserConsent.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def accept(
    db: Session,
    *,
    user_id: uuid.UUID,
    filing_session_id: uuid.UUID,
    consent_definition: ConsentDefinition,
    consent_code_for_audit: str,
) -> tuple[UserConsent, bool]:
    """Returns (row, created). Idempotent: an exact retry (current row is
    already ACCEPTED for this exact consent_definition version) returns it
    unchanged — no new row, no new audit event. Re-acceptance after a
    withdrawal always creates a fresh historical row (never resurrects the
    withdrawn one), mirroring the filing_flag reactivation requirement.
    """
    current = get_current_user_consent(
        db, user_id=user_id, filing_session_id=filing_session_id, consent_definition_id=consent_definition.id
    )
    if current is not None and current.status == UserConsentStatus.ACCEPTED:
        return current, False

    new_row = UserConsent(
        user_id=user_id,
        filing_session_id=filing_session_id,
        consent_definition_id=consent_definition.id,
        status=UserConsentStatus.ACCEPTED,
        is_current=True,
        supersedes_id=current.id if current else None,
    )
    if current is not None:
        current.is_current = False
    db.add(new_row)
    db.flush()  # assign new_row.id before it's used as subject_id below

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.CONSENT_ACCEPTED,
        actor_type=ActorType.USER,
        actor_user_id=user_id,
        filing_session_id=filing_session_id,
        subject_type="user_consent",
        subject_id=new_row.id,
        metadata={"consent_code": consent_code_for_audit, "version_number": consent_definition.version_number},
    )

    db.commit()
    db.refresh(new_row)
    return new_row, True


def withdraw(
    db: Session,
    *,
    user_id: uuid.UUID,
    filing_session_id: uuid.UUID,
    consent_definition: ConsentDefinition,
    consent_code_for_audit: str,
    current: UserConsent,
) -> tuple[UserConsent, bool]:
    """`current` must be the caller's already-fetched, already-ACCEPTED
    current row (the service layer owns the "must have an active acceptance
    to withdraw" business rule). Idempotent: if it's already WITHDRAWN,
    returns it unchanged."""
    if current.status == UserConsentStatus.WITHDRAWN:
        return current, False

    new_row = UserConsent(
        user_id=user_id,
        filing_session_id=filing_session_id,
        consent_definition_id=consent_definition.id,
        status=UserConsentStatus.WITHDRAWN,
        is_current=True,
        supersedes_id=current.id,
    )
    current.is_current = False
    db.add(new_row)
    db.flush()

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.CONSENT_WITHDRAWN,
        actor_type=ActorType.USER,
        actor_user_id=user_id,
        filing_session_id=filing_session_id,
        subject_type="user_consent",
        subject_id=new_row.id,
        metadata={"consent_code": consent_code_for_audit, "version_number": consent_definition.version_number},
    )

    db.commit()
    db.refresh(new_row)
    return new_row, True
