import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt

from app.core.config import get_settings

_BCRYPT_MAX_PASSWORD_BYTES = 72  # bcrypt silently truncates/errors beyond this


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Base for all token validation failures. Callers (app/core/deps.py)
    must never expose str(exc) or any underlying jwt-library exception text
    in an API response — only a fixed, safe message per docs/IMPLEMENTATION_
    PLAN.md Phase 11's "authentication failures leak no unnecessary
    information" requirement."""


class TokenExpiredError(TokenError):
    """The token's `exp` claim has passed — distinguished from other
    failures so a client knows to use its refresh token, not because the
    two cases need different security treatment."""


class TokenInvalidError(TokenError):
    """Malformed, bad signature, wrong token type, or missing required
    claims — deliberately NOT distinguished from each other, so a client (or
    attacker) can't use the error to probe which specific thing is wrong
    with a tampered token."""


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("password exceeds maximum supported length")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format — never a valid match, never a crash.
        return False


def _encode(*, user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta, jti: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": jti,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _encode(
        user_id=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        jti=str(uuid.uuid4()),
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, uuid.UUID, datetime]:
    """Returns (token, jti, expires_at). Unlike the access token, the caller
    persists (jti, expires_at) — see app/repositories/refresh_token.py — so a
    refresh token can be individually revoked (logout, rotation) even though
    its signature alone would otherwise remain valid until `exp`."""
    settings = get_settings()
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    jti = uuid.uuid4()
    token = _encode(user_id=user_id, token_type=TokenType.REFRESH, expires_delta=expires_delta, jti=str(jti))
    expires_at = datetime.now(timezone.utc) + expires_delta
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: TokenType) -> dict:
    """Raises TokenExpiredError or TokenInvalidError on any problem —
    including a syntactically valid, correctly-signed token of the wrong
    type (e.g. a refresh token presented where an access token is required).
    Never returns a payload that hasn't passed every check.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError() from exc

    if payload.get("type") != expected_type.value:
        raise TokenInvalidError()
    if not payload.get("sub") or not payload.get("jti"):
        raise TokenInvalidError()
    return payload
