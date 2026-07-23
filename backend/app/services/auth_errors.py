class AuthError(Exception):
    """Base class for auth service domain errors."""


class InvalidCredentialsError(AuthError):
    """Wrong email OR wrong password — deliberately a single error/message
    for both (see app/api/v1/auth.py), so a client can't enumerate which
    emails are registered."""

    def __init__(self):
        super().__init__("Incorrect email or password")


class EmailAlreadyRegisteredError(AuthError):
    def __init__(self, email: str):
        super().__init__(f"Email {email!r} is already registered")
        self.email = email


class InvalidRefreshTokenError(AuthError):
    """Expired, revoked, already-rotated, or malformed — all one error, all
    one generic client-facing message. What specifically was wrong with the
    refresh token is never distinguished in the response."""

    def __init__(self):
        super().__init__("Invalid refresh token")
