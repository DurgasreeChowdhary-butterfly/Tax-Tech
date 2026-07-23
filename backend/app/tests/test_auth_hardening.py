"""Regression coverage for the Phase 11 authentication hardening audit:
UTC-consistent token timestamps, atomic (race-safe) refresh-token rotation,
the unique constraint on refresh_tokens.jti, production-safe JWT secret
loading, and constant-time login. True concurrent-request races require a
real database with row-level locking — see test_auth_postgres.py for the
Postgres-gated multi-threaded proof; this file covers everything that's
provable against the SQLite unit-test path.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.models.refresh_token import RefreshToken
from app.repositories import refresh_token as refresh_token_repo
from app.repositories.user import create_user
from app.schemas.user import UserCreate
from app.services import auth as auth_service


def _register_and_login(client, email="hardening@example.com", password="TestPassword123!"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()


# --- point 1: UTC consistency -----------------------------------------------


def test_refresh_token_timestamps_are_utc_aware_at_creation(db_session):
    from app.core.security import create_refresh_token

    user = create_user(db_session, UserCreate(email="utc-check@example.com", password="TestPassword123!"))
    _token, jti, expires_at = create_refresh_token(user.id)
    assert expires_at.tzinfo is not None
    assert expires_at.utcoffset() == timedelta(0)


# --- point 3/4/5/6: atomic rotation -----------------------------------------


def test_revoke_if_active_is_a_one_shot_compare_and_swap(db_session):
    """Direct repository-level proof that a second call for the same jti,
    after the first has committed, gets nothing — the primitive refresh
    rotation and logout both build their race-safety on."""
    user = create_user(db_session, UserCreate(email="cas@example.com", password="TestPassword123!"))
    jti = uuid.uuid4()
    refresh_token_repo.create_refresh_token(
        db_session, user_id=user.id, jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )

    first = refresh_token_repo.revoke_if_active(db_session, jti)
    assert first is not None
    assert first.revoked_at is not None

    second = refresh_token_repo.revoke_if_active(db_session, jti)
    assert second is None  # already revoked — not re-revoked, not returned again


def test_revoke_if_active_returns_none_for_unknown_jti(db_session):
    assert refresh_token_repo.revoke_if_active(db_session, uuid.uuid4()) is None


def test_expired_refresh_token_is_rejected_by_service_and_marked_revoked(client, db_session):
    """A refresh token past its expires_at must never mint a new pair — even
    though revoke_if_active itself doesn't filter on expiry (it still flips
    revoked_at as harmless bookkeeping), the service layer must reject it."""
    tokens = _register_and_login(client, email="expired-refresh@example.com")
    from app.core.security import decode_token, TokenType

    payload = decode_token(tokens["refresh_token"], expected_type=TokenType.REFRESH)
    jti = uuid.UUID(payload["jti"])

    record = db_session.query(RefreshToken).filter_by(jti=jti).one()
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    from app.services.auth_errors import InvalidRefreshTokenError

    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh_tokens(db_session, tokens["refresh_token"])

    db_session.refresh(record)
    assert record.revoked_at is not None  # still gets marked dead, just never issues a new pair


def test_logout_then_refresh_with_same_token_is_rejected_not_resurrected(client):
    tokens = _register_and_login(client, email="logout-then-refresh@example.com")
    logout_resp = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout_resp.status_code == 204

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 401

    # Confirm it stays dead — repeating the attempt doesn't un-revoke it or
    # succeed on a later try.
    refresh_resp_2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp_2.status_code == 401


# --- point 7: unique constraint ---------------------------------------------


def test_refresh_tokens_jti_has_a_unique_constraint(db_session):
    user = create_user(db_session, UserCreate(email="unique-jti@example.com", password="TestPassword123!"))
    jti = uuid.uuid4()
    refresh_token_repo.create_refresh_token(
        db_session, user_id=user.id, jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db_session.add(RefreshToken(user_id=user.id, jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- point 9: JWT secret production-safety ----------------------------------


def test_settings_rejects_insecure_default_secret_outside_development():
    with pytest.raises(ValidationError):
        Settings(environment="production")

    with pytest.raises(ValidationError):
        Settings(environment="staging")


def test_settings_allows_default_secret_in_development():
    settings = Settings(environment="development")
    assert settings.jwt_secret_key  # the placeholder — fine in development


def test_settings_allows_production_with_a_real_secret():
    settings = Settings(environment="production", jwt_secret_key="a-real-randomly-generated-secret")
    assert settings.environment == "production"


# --- point 10: constant-time login -------------------------------------------


def test_authenticate_runs_password_hashing_even_for_unknown_email(db_session, monkeypatch):
    """The timing-safety fix only works if verify_password is actually
    invoked on the unknown-email path — assert that directly rather than
    asserting on wall-clock timing, which is flaky in CI."""
    calls = []
    from app.services import auth as auth_service_module

    original = auth_service_module.verify_password

    def _spy(password, hashed):
        calls.append(hashed)
        return original(password, hashed)

    monkeypatch.setattr(auth_service_module, "verify_password", _spy)

    from app.services.auth_errors import InvalidCredentialsError

    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate(db_session, email="definitely-not-registered@example.com", password="whatever123")

    assert len(calls) == 1
    assert calls[0] == auth_service_module._TIMING_SAFE_DUMMY_HASH


def test_unknown_email_is_rejected_even_if_password_guesses_the_dummy_plaintext(db_session):
    """Even in the (already cryptographically absurd) case where a caller's
    password happens to verify against the dummy hash, authenticate() must
    still reject an unknown email — `user is None` is checked independently
    of password_matches."""
    from app.services.auth_errors import InvalidCredentialsError

    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate(
            db_session,
            email="still-not-registered@example.com",
            password="timing-safety-placeholder-not-a-real-password",
        )
