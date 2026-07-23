import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TokenExpiredError, TokenInvalidError, TokenType, decode_token
from app.models.filing_session import FilingSession
from app.models.user import User
from app.repositories.filing_session import get_filing_session
from app.repositories.user import get_user

_bearer_scheme = HTTPBearer(auto_error=False)
_WWW_AUTHENTICATE_HEADER = {"WWW-Authenticate": "Bearer"}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The sole way any protected endpoint learns who is calling. Never
    accepts a user id from the request itself — only from a verified JWT's
    `sub` claim. Every failure mode (missing header, expired, malformed, bad
    signature, unknown user) returns one of two fixed, generic 401 messages
    — see app/core/security.py's TokenExpiredError/TokenInvalidError split
    for why expiry alone gets a distinguishable message.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers=_WWW_AUTHENTICATE_HEADER)

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except TokenExpiredError as exc:
        raise HTTPException(status_code=401, detail="Token has expired", headers=_WWW_AUTHENTICATE_HEADER) from exc
    except TokenInvalidError as exc:
        raise HTTPException(
            status_code=401, detail="Could not validate credentials", headers=_WWW_AUTHENTICATE_HEADER
        ) from exc

    user = get_user(db, uuid.UUID(payload["sub"]))
    if user is None:
        # The token is validly signed but names a user that no longer
        # exists — same generic message as any other invalid token.
        raise HTTPException(
            status_code=401, detail="Could not validate credentials", headers=_WWW_AUTHENTICATE_HEADER
        )
    return user


def get_owned_filing_session(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FilingSession:
    """Route-protection + ownership enforcement in one dependency, reusable
    across every `/filing-sessions/{filing_session_id}/...` router. Returns
    404 — never 403 — whether the session doesn't exist at all or belongs to
    a different user, so a client can never distinguish "not yours" from
    "doesn't exist" (no confirmation that another user's session id is
    real). This is the single place cross-user access is rejected; every
    endpoint that depends on it inherits the guarantee without repeating the
    check itself.
    """
    filing_session = get_filing_session(db, filing_session_id)
    if filing_session is None or filing_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Filing session {filing_session_id} not found")
    return filing_session
