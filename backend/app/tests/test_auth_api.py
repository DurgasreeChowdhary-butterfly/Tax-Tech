import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.repositories import audit_log as audit_log_repo
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.tests.conftest import auth_headers


def _register(client, email="auth-user@example.com", password="TestPassword123!"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def _login(client, email="auth-user@example.com", password="TestPassword123!"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- registration ----------------------------------------------------------


def test_register_creates_user_without_exposing_password(client):
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "auth-user@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(client):
    _register(client)
    resp = _register(client)
    assert resp.status_code == 409


def test_register_short_password_rejected(client):
    resp = client.post("/api/v1/auth/register", json={"email": "short-pw@example.com", "password": "short"})
    assert resp.status_code == 422


# --- login -------------------------------------------------------------


def test_successful_login_returns_token_pair(client):
    _register(client)
    resp = _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["access_token"] != body["refresh_token"]


def test_invalid_password_returns_401(client):
    _register(client)
    resp = _login(client, password="WrongPassword123!")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


def test_invalid_email_returns_same_generic_401_as_wrong_password(client):
    """No user enumeration: an unregistered email and a wrong password for a
    real account must be indistinguishable to the caller."""
    _register(client)
    unknown_email_resp = _login(client, email="nobody@example.com")
    wrong_password_resp = _login(client, password="WrongPassword123!")

    assert unknown_email_resp.status_code == wrong_password_resp.status_code == 401
    assert unknown_email_resp.json() == wrong_password_resp.json()


# --- route protection / token validation -----------------------------------


def test_health_endpoint_requires_no_auth(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_protected_endpoint_rejects_missing_token(client, db_session):
    user = create_user(db_session, UserCreate(email="missing-token@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    resp = client.get(f"/api/v1/filing-sessions/{session.id}/decision-state")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_protected_endpoint_rejects_malformed_token(client, db_session):
    user = create_user(db_session, UserCreate(email="malformed-token@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    resp = client.get(
        f"/api/v1/filing-sessions/{session.id}/decision-state",
        headers={"Authorization": "Bearer not-a-real-jwt-at-all"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_protected_endpoint_rejects_invalid_signature(client, db_session):
    user = create_user(db_session, UserCreate(email="bad-sig@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    settings = get_settings()
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": str(user.id), "type": "access", "iat": now, "exp": now + timedelta(minutes=5), "jti": str(uuid.uuid4())},
        "a-completely-different-secret-key",
        algorithm=settings.jwt_algorithm,
    )
    resp = client.get(
        f"/api/v1/filing-sessions/{session.id}/decision-state", headers={"Authorization": f"Bearer {forged}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_protected_endpoint_rejects_expired_token(client, db_session):
    user = create_user(db_session, UserCreate(email="expired-token@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": str(user.id), "type": "access", "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=1), "jti": str(uuid.uuid4()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = client.get(
        f"/api/v1/filing-sessions/{session.id}/decision-state", headers={"Authorization": f"Bearer {expired}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token has expired"


def test_protected_endpoint_rejects_refresh_token_used_as_access_token(client, db_session):
    user = create_user(db_session, UserCreate(email="wrong-type@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    refresh_token, _jti, _exp = create_refresh_token(user.id)

    resp = client.get(
        f"/api/v1/filing-sessions/{session.id}/decision-state", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_protected_endpoint_rejects_token_for_deleted_user(client, db_session):
    user = create_user(db_session, UserCreate(email="ghost-user@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    token = create_access_token(user.id)

    db_session.delete(session)
    db_session.delete(user)
    db_session.commit()

    resp = client.get(f"/api/v1/filing-sessions/{uuid.uuid4()}/decision-state", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_authenticated_endpoint_success(client, db_session):
    user = create_user(db_session, UserCreate(email="me-user@example.com", password="TestPassword123!"))
    resp = client.get("/api/v1/auth/me", headers=auth_headers(user.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me-user@example.com"
    assert "password" not in body and "hashed_password" not in body


def test_me_endpoint_rejects_unauthenticated_request(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# --- ownership / cross-user rejection ---------------------------------------


def test_cross_user_token_cannot_read_another_users_filing_session(client, db_session):
    owner = create_user(db_session, UserCreate(email="owner@example.com", password="TestPassword123!"))
    owned_session = create_filing_session(db_session, FilingSessionCreate(user_id=owner.id, assessment_year="2026-27"))
    intruder = create_user(db_session, UserCreate(email="intruder@example.com", password="TestPassword123!"))

    resp = client.get(f"/api/v1/filing-sessions/{owned_session.id}/decision-state", headers=auth_headers(intruder.id))
    assert resp.status_code == 404  # never 403 — existence not confirmed either


def test_own_session_still_accessible_with_own_token(client, db_session):
    owner = create_user(db_session, UserCreate(email="self-owner@example.com", password="TestPassword123!"))
    owned_session = create_filing_session(db_session, FilingSessionCreate(user_id=owner.id, assessment_year="2026-27"))

    resp = client.get(f"/api/v1/filing-sessions/{owned_session.id}/decision-state", headers=auth_headers(owner.id))
    assert resp.status_code == 200


# --- refresh / logout lifecycle ---------------------------------------------


def test_refresh_issues_new_pair_and_rotates_old_refresh_token(client):
    _register(client)
    login_body = _login(client).json()

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert refresh_resp.status_code == 200
    new_body = refresh_resp.json()
    assert new_body["access_token"] != login_body["access_token"]
    assert new_body["refresh_token"] != login_body["refresh_token"]

    # The original (now-rotated) refresh token must be dead — reuse rejected.
    reuse_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["detail"] == "Invalid refresh token"

    # The NEW refresh token still works.
    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": new_body["refresh_token"]})
    assert second_refresh.status_code == 200


def test_refresh_rejects_malformed_or_access_token(client):
    _register(client)
    login_body = _login(client).json()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401

    # An access token is not a refresh token, even though it's validly signed.
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": login_body["access_token"]})
    assert resp2.status_code == 401


def test_logout_revokes_refresh_token(client):
    _register(client)
    login_body = _login(client).json()

    logout_resp = client.post("/api/v1/auth/logout", json={"refresh_token": login_body["refresh_token"]})
    assert logout_resp.status_code == 204

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert refresh_resp.status_code == 401


def test_logout_is_idempotent_and_never_errors_on_unknown_token(client):
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 204


# --- audit actor identity ---------------------------------------------------


def test_audit_actor_identity_matches_authenticated_user(client, db_session, questionnaire_fixture):
    version, questions = questionnaire_fixture
    user = create_user(db_session, UserCreate(email="audited-user@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    q1 = questions["has_other_income"]

    resp = client.post(
        f"/api/v1/filing-sessions/{session.id}/questionnaire/answers",
        json={"question_id": str(q1.id), "value": True},
        headers=auth_headers(user.id),
    )
    assert resp.status_code == 200

    events = audit_log_repo.list_for_filing_session(db_session, session.id)
    answer_event = next(e for e in events if e.event_code.value == "QUESTION_ANSWER_CREATED")
    assert answer_event.actor_user_id == user.id


# --- regression: existing consent/document/calculation ownership -----------


def test_consent_endpoint_enforces_ownership(client, db_session, consent_definitions_v1):
    owner = create_user(db_session, UserCreate(email="consent-owner@example.com", password="TestPassword123!"))
    owned_session = create_filing_session(db_session, FilingSessionCreate(user_id=owner.id, assessment_year="2026-27"))
    intruder = create_user(db_session, UserCreate(email="consent-intruder@example.com", password="TestPassword123!"))

    resp = client.get(f"/api/v1/filing-sessions/{owned_session.id}/consents", headers=auth_headers(intruder.id))
    assert resp.status_code == 404

    resp_owner = client.get(f"/api/v1/filing-sessions/{owned_session.id}/consents", headers=auth_headers(owner.id))
    assert resp_owner.status_code == 200
