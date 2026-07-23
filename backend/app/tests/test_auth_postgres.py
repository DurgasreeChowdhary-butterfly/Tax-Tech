"""PostgreSQL-only verification of Phase 11 auth against a real database:
registration, login, protected-endpoint ownership enforcement, and audit
actor identity. Mirrors test_alembic_postgres.py / test_audit_postgres.py's
environment-variable-gated pattern exactly — the SQLite unit-test path
(test_auth_api.py) already covers the same behavior against the in-memory
test database.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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
def pg_client():
    """A TestClient whose `get_db` dependency is overridden to talk to the
    REAL PostgreSQL container — not the SQLite in-memory path every other
    test file uses. app.core.database.engine is a module-level singleton
    bound at first import, so pointing requests at Postgres requires an
    explicit dependency override (mirrors conftest.py's `client` fixture,
    just against a different engine) rather than an env var / settings
    change after the fact.
    """
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(POSTGRES_TEST_URL.replace("postgresql+psycopg2", "postgresql"))
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


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


def test_register_login_and_ownership_against_real_postgres(pg_client, pg_session):
    unique = uuid.uuid4().hex[:8]
    owner_email = f"pg-owner-{unique}@example.com"
    intruder_email = f"pg-intruder-{unique}@example.com"

    reg = pg_client.post("/api/v1/auth/register", json={"email": owner_email, "password": "OwnerPassword123!"})
    assert reg.status_code == 201
    pg_client.post("/api/v1/auth/register", json={"email": intruder_email, "password": "IntruderPassword123!"})

    login = pg_client.post("/api/v1/auth/login", json={"email": owner_email, "password": "OwnerPassword123!"})
    assert login.status_code == 200
    owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    bad_login = pg_client.post("/api/v1/auth/login", json={"email": owner_email, "password": "wrong"})
    assert bad_login.status_code == 401

    intruder_login = pg_client.post(
        "/api/v1/auth/login", json={"email": intruder_email, "password": "IntruderPassword123!"}
    )
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}

    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import get_user_by_email
    from app.schemas.filing_session import FilingSessionCreate

    owner = get_user_by_email(pg_session, owner_email)
    owned_session = create_filing_session(pg_session, FilingSessionCreate(user_id=owner.id, assessment_year="2026-27"))

    # Owner can read their own session.
    resp = pg_client.get(f"/api/v1/filing-sessions/{owned_session.id}/decision-state", headers=owner_headers)
    assert resp.status_code == 200

    # A different, validly-authenticated user is rejected — 404, not 403.
    resp = pg_client.get(f"/api/v1/filing-sessions/{owned_session.id}/decision-state", headers=intruder_headers)
    assert resp.status_code == 404

    # No token at all is rejected before any ownership check runs.
    resp = pg_client.get(f"/api/v1/filing-sessions/{owned_session.id}/decision-state")
    assert resp.status_code == 401


def test_audit_actor_identity_against_real_postgres(pg_client, pg_session):
    unique = uuid.uuid4().hex[:8]
    email = f"pg-audit-actor-{unique}@example.com"
    pg_client.post("/api/v1/auth/register", json={"email": email, "password": "AuditPassword123!"})
    login = pg_client.post("/api/v1/auth/login", json={"email": email, "password": "AuditPassword123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    from app.models.enums import QuestionType
    from app.repositories import questionnaire as questionnaire_repo
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import get_user_by_email
    from app.schemas.filing_session import FilingSessionCreate

    user = get_user_by_email(pg_session, email)
    session = create_filing_session(pg_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    version = questionnaire_repo.create_questionnaire_version(pg_session, assessment_year="2026-27", version_number=1)
    q1 = questionnaire_repo.add_question(
        pg_session, version, key="has_other_income", order_index=1, question_type=QuestionType.BOOLEAN,
        prompt="Do you have other income?",
    )
    pg_session.refresh(version)
    questionnaire_repo.publish_questionnaire_version(pg_session, version)

    resp = pg_client.post(
        f"/api/v1/filing-sessions/{session.id}/questionnaire/answers",
        json={"question_id": str(q1.id), "value": True},
        headers=headers,
    )
    assert resp.status_code == 200

    from app.repositories import audit_log as audit_log_repo

    events = audit_log_repo.list_for_filing_session(pg_session, session.id)
    answer_event = next(e for e in events if e.event_code.value == "QUESTION_ANSWER_CREATED")
    assert answer_event.actor_user_id == user.id


def test_concurrent_updates_on_same_refresh_token_are_serialized_by_row_lock(pg_session):
    """Deterministic (not timing-dependent) proof of the exact mechanism
    refresh_token_repo.revoke_if_active relies on: two transactions racing
    the same 'UPDATE ... WHERE jti = :jti AND revoked_at IS NULL' on
    PostgreSQL cannot both succeed. Thread B is forced to genuinely block on
    Thread A's uncommitted row lock (proven via an Event, not a sleep/guess),
    and once A commits, B's WHERE clause is re-evaluated against the
    post-commit row and correctly matches zero rows. This is the hardening-
    audit finding: the OLD code (separate SELECT then UPDATE) had a real gap
    here — two concurrent readers could both observe "not yet revoked"
    before either wrote — which is exactly what this test would have caught.
    """
    import threading
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import create_engine, text

    from app.repositories import refresh_token as refresh_token_repo
    from app.repositories.user import create_user
    from app.schemas.user import UserCreate

    user = create_user(
        pg_session, UserCreate(email=f"pg-race-{uuid.uuid4().hex[:8]}@example.com", password="RacePassword123!")
    )
    jti = uuid.uuid4()
    refresh_token_repo.create_refresh_token(
        pg_session, user_id=user.id, jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )

    pg_url = POSTGRES_TEST_URL.replace("postgresql+psycopg2", "postgresql")
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    conn_a = engine_a.connect()
    conn_b = engine_b.connect()

    update_sql = text("UPDATE refresh_tokens SET revoked_at = now() WHERE jti = :jti AND revoked_at IS NULL")

    a_locked = threading.Event()
    release_a = threading.Event()
    b_started = threading.Event()
    b_finished = threading.Event()
    row_counts: dict[str, int] = {}

    def _run_a():
        trans = conn_a.begin()
        result = conn_a.execute(update_sql, {"jti": str(jti)})
        row_counts["a"] = result.rowcount
        a_locked.set()
        release_a.wait(timeout=5)
        trans.commit()

    def _run_b():
        trans = conn_b.begin()
        b_started.set()
        result = conn_b.execute(update_sql, {"jti": str(jti)})  # blocks here until A commits
        row_counts["b"] = result.rowcount
        trans.commit()
        b_finished.set()

    thread_a = threading.Thread(target=_run_a)
    thread_a.start()
    assert a_locked.wait(timeout=5), "thread A never acquired the row lock"

    thread_b = threading.Thread(target=_run_b)
    thread_b.start()
    assert b_started.wait(timeout=5)

    # B must still be blocked on A's uncommitted lock — if this fails, B did
    # NOT actually contend for the row, and the test below would be vacuous.
    assert not b_finished.wait(timeout=1), "thread B completed without waiting for thread A's lock"

    release_a.set()
    thread_a.join(timeout=5)
    thread_b.join(timeout=5)

    assert row_counts["a"] == 1  # A won: it revoked the row
    assert row_counts["b"] == 0  # B lost: post-commit WHERE clause matched nothing

    conn_a.close()
    conn_b.close()
    engine_a.dispose()
    engine_b.dispose()


def test_concurrent_refresh_requests_with_same_token_only_one_succeeds(pg_client):
    """End-to-end version of the same property through the real HTTP
    endpoint and application dependency-injection path (not just the raw
    SQL statement) — two threads, two independent TestClient instances
    (separate DB sessions per request, like real concurrent requests),
    racing POST /api/v1/auth/refresh with the identical refresh token.
    """
    import threading

    from app.main import app

    unique = uuid.uuid4().hex[:8]
    email = f"pg-http-race-{unique}@example.com"
    pg_client.post("/api/v1/auth/register", json={"email": email, "password": "HttpRacePassword123!"})
    login = pg_client.post("/api/v1/auth/login", json={"email": email, "password": "HttpRacePassword123!"})
    refresh_token = login.json()["refresh_token"]

    barrier = threading.Barrier(2)
    statuses: list[int | None] = [None, None]

    def _attempt(index: int) -> None:
        thread_client = TestClient(app)  # own portal; shares app.dependency_overrides with pg_client
        barrier.wait(timeout=5)
        resp = thread_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        statuses[index] = resp.status_code

    threads = [threading.Thread(target=_attempt, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(statuses) == [200, 401], f"expected exactly one success and one rejection, got {statuses}"
