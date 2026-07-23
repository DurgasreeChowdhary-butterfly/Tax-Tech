"""Creates (idempotently) ONE stable demo user for manual handoff testing —
NOT part of the product API surface, and not run automatically by anything.

There is no registration UI in the frontend yet (only the backend
`/api/v1/auth/register` endpoint exists — see docs/IMPLEMENTATION_PLAN.md
Phase 12/13 scope), so this script is the supported way to get a login that
can walk the full guided journey (questionnaire -> document upload -> review
cards -> regime comparison -> tax summary) by hand.

Safe to re-run: if the demo user and its filing session already exist, this
prints the same credentials/session id again without creating duplicates.

Usage:
    python scripts/seed_demo_user.py

Prints a single JSON object on stdout: {"email", "password",
"filing_session_id"}.
"""

import json

from app.core.database import Base, SessionLocal, engine
from app.models.filing_session import FilingSession
from app.repositories import user as user_repo
from app.schemas.user import UserCreate
from fixture_environment import ASSESSMENT_YEAR, create_supported_filing_session, ensure_environment

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "DemoPassword123!"


def _get_existing_filing_session(db, user_id):
    return (
        db.query(FilingSession)
        .filter(FilingSession.user_id == user_id, FilingSession.assessment_year == ASSESSMENT_YEAR)
        .first()
    )


def main() -> None:
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        ensure_environment(db)

        user = user_repo.get_user_by_email(db, DEMO_EMAIL)
        if user is None:
            user = user_repo.create_user(db, UserCreate(email=DEMO_EMAIL, password=DEMO_PASSWORD))

        session = _get_existing_filing_session(db, user.id)
        if session is None:
            session = create_supported_filing_session(db, user)

        print(json.dumps({
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            "filing_session_id": str(session.id),
        }))
    finally:
        db.close()


if __name__ == "__main__":
    main()
