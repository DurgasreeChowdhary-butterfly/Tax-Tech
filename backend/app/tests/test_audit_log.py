import uuid
from decimal import Decimal

import pytest

from app.audit import service as audit_service
from app.audit.service import UnsafeAuditMetadataError
from app.models.audit_log import AuditLog
from app.models.deduction import Deduction
from app.models.enums import ActorType, AuditEventCode
from app.repositories import audit_log as audit_log_repo
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate


@pytest.fixture()
def filing_session(db_session):
    user = create_user(db_session, UserCreate(email="audit-log@example.com", password="TestPassword123!"))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def test_stage_event_requires_actor_user_id_for_user_actor(db_session, filing_session):
    with pytest.raises(ValueError):
        audit_service.stage_event(
            db_session,
            event_code=AuditEventCode.DEDUCTION_CLAIMED,
            actor_type=ActorType.USER,
            actor_user_id=None,
            filing_session_id=filing_session.id,
        )


def test_system_actor_needs_no_actor_user_id(db_session, filing_session):
    event = audit_service.stage_event(
        db_session,
        event_code=AuditEventCode.FILING_FLAG_ACTIVATED,
        actor_type=ActorType.SYSTEM,
        filing_session_id=filing_session.id,
        subject_type="filing_flag",
        subject_id=uuid.uuid4(),
        metadata={"flag_code": "SOME_FLAG"},
    )
    db_session.commit()

    assert event.actor_type == ActorType.SYSTEM
    assert event.actor_user_id is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"pan": "ABCDE1234F"},
        {"claimed_amount": "1000.00"},
        {"verified_value": "50000"},
        {"storage_key": "filing-sessions/x/y"},
        {"auth_token": "abc"},
        {"password": "hunter2"},
        {"raw_exception": "boom"},
        {"too": "many", "keys": 1, "than": 2, "the": 3, "cap": 4, "allows": 5, "for": 6, "this": 7, "call": 8},
        {"blob": "x" * 500},
        {"nested": {"a": 1}},
    ],
)
def test_unsafe_metadata_is_rejected(db_session, filing_session, metadata):
    # filing_session's own FILING_SESSION_CREATED event is already committed
    # by fixture setup — assert on the delta, not an absolute zero count.
    before = db_session.query(AuditLog).count()

    with pytest.raises(UnsafeAuditMetadataError):
        audit_service.stage_event(
            db_session,
            event_code=AuditEventCode.DEDUCTION_CLAIMED,
            actor_type=ActorType.SYSTEM,
            filing_session_id=filing_session.id,
            metadata=metadata,
        )
    db_session.rollback()
    assert db_session.query(AuditLog).count() == before


def test_audit_log_repo_exposes_no_update_or_delete():
    """Application-layer append-only guarantee: there is simply no function
    to call. (DB-level enforcement on PostgreSQL is verified separately —
    see test_audit_postgres.py.)"""
    assert not hasattr(audit_log_repo, "update_event")
    assert not hasattr(audit_log_repo, "delete_event")


def test_rollback_after_staged_event_leaves_no_domain_row_and_no_audit_row(db_session, filing_session):
    """Models a failure occurring after an event is staged (added+flushed)
    but before the caller's own commit — e.g. an exception raised by a later
    step in the same repository function. Nothing from this transaction may
    survive the rollback: neither the domain write nor its audit event."""
    audit_before = db_session.query(AuditLog).count()  # includes fixture's FILING_SESSION_CREATED event

    row = Deduction(filing_session_id=filing_session.id, code="SECTION_80C", claimed_amount=Decimal("1000.00"))
    db_session.add(row)
    db_session.flush()

    audit_service.stage_event(
        db_session,
        event_code=AuditEventCode.DEDUCTION_CLAIMED,
        actor_type=ActorType.USER,
        actor_user_id=filing_session.user_id,
        filing_session_id=filing_session.id,
        subject_type="deduction",
        subject_id=row.id,
        metadata={"code": "SECTION_80C"},
    )

    db_session.rollback()

    assert db_session.query(Deduction).count() == 0
    assert db_session.query(AuditLog).count() == audit_before
