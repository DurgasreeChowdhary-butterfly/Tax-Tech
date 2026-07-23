"""PostgreSQL-only verification of the DB-level append-only/immutability
protections added in the Phase 10 migration (docs/IMPLEMENTATION_PLAN.md
Phase 10: "PostgreSQL: enforce append-only behaviour with DB-level
protection"). The SQLite test path can't exercise these — SQLite has no
triggers rejecting arbitrary UPDATE/DELETE the way the Phase 10 migration's
PL/pgSQL triggers do — so this mirrors test_alembic_postgres.py's
environment-variable-gated pattern exactly.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import InternalError, OperationalError
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
POSTGRES_TEST_URL = os.environ.get("PHASE2_POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="Set PHASE2_POSTGRES_TEST_URL to a real PostgreSQL DSN to run this check.",
)


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": POSTGRES_TEST_URL},
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module", autouse=True)
def _migrated_schema():
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr


@pytest.fixture()
def pg_session():
    engine = create_engine(POSTGRES_TEST_URL.replace("postgresql+psycopg2", "postgresql"))
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_direct_update_on_audit_logs_is_rejected(pg_session):
    from app.audit import service as audit_service
    from app.models.enums import ActorType, AuditEventCode
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate

    user = create_user(pg_session, UserCreate(email=f"pg-audit-{uuid.uuid4()}@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(pg_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    event = audit_service.stage_event(
        pg_session,
        event_code=AuditEventCode.CONSENT_ACCEPTED,
        actor_type=ActorType.USER,
        actor_user_id=user.id,
        filing_session_id=filing_session.id,
        metadata={"consent_code": "DATA_PROCESSING"},
    )
    pg_session.commit()

    with pytest.raises((InternalError, OperationalError)) as excinfo:
        pg_session.execute(text("UPDATE audit_logs SET subject_type = 'tampered' WHERE id = :id"), {"id": event.id})
        pg_session.commit()
    assert "append-only" in str(excinfo.value).lower()
    pg_session.rollback()


def test_direct_delete_on_audit_logs_is_rejected(pg_session):
    from app.audit import service as audit_service
    from app.models.enums import ActorType, AuditEventCode
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate

    user = create_user(pg_session, UserCreate(email=f"pg-audit-del-{uuid.uuid4()}@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(pg_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    event = audit_service.stage_event(
        pg_session,
        event_code=AuditEventCode.CONSENT_WITHDRAWN,
        actor_type=ActorType.USER,
        actor_user_id=user.id,
        filing_session_id=filing_session.id,
        metadata={"consent_code": "DATA_PROCESSING"},
    )
    pg_session.commit()

    with pytest.raises((InternalError, OperationalError)) as excinfo:
        pg_session.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": event.id})
        pg_session.commit()
    assert "append-only" in str(excinfo.value).lower()
    pg_session.rollback()


def test_direct_update_on_published_consent_definition_is_rejected(pg_session):
    from app.services import consent as consent_service

    definitions = consent_service.seed_v1_consent_definitions(pg_session)
    published = definitions[0]

    with pytest.raises((InternalError, OperationalError)) as excinfo:
        pg_session.execute(text("UPDATE consent_definitions SET title = 'tampered' WHERE id = :id"), {"id": published.id})
        pg_session.commit()
    assert "immutable" in str(excinfo.value).lower()
    pg_session.rollback()
