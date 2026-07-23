import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories import refresh_token as refresh_token_repo
from app.repositories import user as user_repo
from app.schemas.user import UserCreate
from app.services.auth_errors import EmailAlreadyRegisteredError, InvalidCredentialsError, InvalidRefreshTokenError


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


# A fixed, valid-format bcrypt hash that matches no real password — computed
# once at import time and used purely to make the "no such user" path pay
# the same bcrypt cost as the "wrong password" path (see authenticate()).
# Its actual value is irrelevant beyond being a hash verify_password can run
# against without erroring; it is never compared against a real account.
_TIMING_SAFE_DUMMY_HASH = hash_password("timing-safety-placeholder-not-a-real-password")


def register_user(db: Session, *, email: str, password: str) -> User:
    if user_repo.get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegisteredError(email)
    return user_repo.create_user(db, UserCreate(email=email, password=password))


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Same InvalidCredentialsError (and, at the API layer, the same HTTP
    response) whether the email doesn't exist or the password is wrong —
    never lets a client distinguish "no such user" from "wrong password".

    That guarantee has to hold for *timing*, not just the response body: an
    unknown email must not short-circuit before the bcrypt verify runs, or
    the "no such user" path becomes measurably faster than "wrong password"
    (bcrypt is deliberately slow, ~100ms+) and an attacker can enumerate
    valid emails purely by timing responses, even though the two responses
    are byte-identical. verify_password always runs — against the real hash
    if the user exists, against a fixed dummy hash otherwise — so both paths
    pay the same cost.
    """
    user = user_repo.get_user_by_email(db, email)
    hashed_password = user.hashed_password if user is not None else _TIMING_SAFE_DUMMY_HASH
    password_matches = verify_password(password, hashed_password)
    if user is None or not password_matches:
        raise InvalidCredentialsError()
    return user


def _issue_token_pair(db: Session, user_id: uuid.UUID) -> TokenPair:
    access = create_access_token(user_id)
    refresh, jti, expires_at = create_refresh_token(user_id)
    refresh_token_repo.create_refresh_token(db, user_id=user_id, jti=jti, expires_at=expires_at)
    return TokenPair(access_token=access, refresh_token=refresh)


def login(db: Session, *, email: str, password: str) -> TokenPair:
    user = authenticate(db, email=email, password=password)
    return _issue_token_pair(db, user.id)


def refresh_tokens(db: Session, refresh_token_str: str) -> TokenPair:
    """Rotation: the presented refresh token is atomically revoked (see
    refresh_token_repo.revoke_if_active) before its replacement is minted,
    so it can never be used a second time — a stolen-but-already-used
    refresh token is dead on arrival. The revoke is a single UPDATE ...
    WHERE revoked_at IS NULL, so if two requests race on the same token,
    exactly one of them observes the revocation as "mine" and proceeds to
    issue a new pair; the other gets None back and is rejected — never two
    valid pairs minted from one old token, no matter how the requests
    interleave (a plain read-then-write here would allow that).
    """
    try:
        payload = decode_token(refresh_token_str, expected_type=TokenType.REFRESH)
    except (TokenExpiredError, TokenInvalidError) as exc:
        raise InvalidRefreshTokenError() from exc

    jti = uuid.UUID(payload["jti"])
    record = refresh_token_repo.revoke_if_active(db, jti)
    if record is None:
        raise InvalidRefreshTokenError()
    if refresh_token_repo.is_expired(record):
        # Already revoked above (harmless bookkeeping) — but an expired
        # token must never mint a new pair, whether or not it was also due
        # for rotation.
        raise InvalidRefreshTokenError()

    return _issue_token_pair(db, record.user_id)


def logout(db: Session, refresh_token_str: str) -> None:
    """Always a no-op success from the caller's point of view — an already-
    invalid/expired/unknown refresh token is already unusable, so there is
    nothing meaningful to report back either way (avoids leaking whether a
    given token was ever valid). Uses the same atomic revoke_if_active as
    rotation, so a logout racing a concurrent refresh of the same token
    can't lose the race silently: whichever of the two reaches the database
    first wins the revoke, and the other is consistently rejected — logout
    can never appear to succeed while a concurrent refresh still mints a
    fresh pair from the same now-revoked token.
    """
    try:
        payload = decode_token(refresh_token_str, expected_type=TokenType.REFRESH)
    except (TokenExpiredError, TokenInvalidError):
        return

    jti = uuid.UUID(payload["jti"])
    refresh_token_repo.revoke_if_active(db, jti)
