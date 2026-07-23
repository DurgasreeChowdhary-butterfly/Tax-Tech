"""Phase 13 dev/E2E fixture seeding — NOT part of the product API surface.

Creates one fresh, randomly-named user + a SUPPORTED-eligible filing session
(see fixture_environment.py) for frontend/e2e/guided-journey.spec.ts to drive
live through the real UI: upload -> extraction -> review cards ->
completion -> regime comparison -> tax summary.

For a STABLE, documented login to explore the same journey by hand, use
seed_demo_user.py instead — this script intentionally mints a new user every
run so repeated E2E runs never collide on a unique-email constraint.

Usage:
    python scripts/seed_phase13_data.py

Prints a single JSON object on stdout: {"email", "password",
"filing_session_id"}.
"""

import json
import uuid

from app.core.database import Base, SessionLocal, engine
from app.repositories import user as user_repo
from app.schemas.user import UserCreate
from fixture_environment import create_supported_filing_session, ensure_environment

SEED_PASSWORD = "SeedDevPassword123!"


def main() -> None:
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        ensure_environment(db)

        email = f"e2e-phase13-{uuid.uuid4()}@example.com"
        user = user_repo.create_user(db, UserCreate(email=email, password=SEED_PASSWORD))
        session = create_supported_filing_session(db, user)

        print(json.dumps({
            "email": email,
            "password": SEED_PASSWORD,
            "filing_session_id": str(session.id),
        }))
    finally:
        db.close()


if __name__ == "__main__":
    main()
