"""Dev/E2E fixture seeding — NOT part of the product API surface.

Creates one user (real bcrypt-hashed password, so it can log in through the
real `/api/v1/auth/login` endpoint) plus one filing session, and — the first
time it runs against a given database — publishes the Phase 3 "mini question
graph" (the same 5-question graph as
`backend/app/tests/conftest.py::questionnaire_fixture`) for assessment year
2026-27 so filing sessions have something to bind to.

Used by the frontend's Playwright E2E happy-path test
(frontend/e2e/questionnaire.spec.ts) to get a real user + filing session to
drive, since Phase 12 must exercise the questionnaire runner against the real
backend rather than a mock. Not imported by application code and not wired to
any endpoint — this is operator/test tooling only.

Usage:
    python scripts/seed_dev_data.py

Prints a single JSON object on stdout: {"email", "password",
"filing_session_id"}. Reads DATABASE_URL the same way the app does (via
app.core.config.Settings / .env), so point it at whatever database the
backend under test is using.
"""

import json
import uuid

from app.core.database import Base, SessionLocal, engine
from app.models import enums
from app.repositories import filing_session as filing_session_repo
from app.repositories import questionnaire as questionnaire_repo
from app.repositories import user as user_repo
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate

ASSESSMENT_YEAR = "2026-27"
SEED_PASSWORD = "SeedDevPassword123!"


def _ensure_mini_question_graph(db) -> None:
    if questionnaire_repo.get_published_version_for_assessment_year(db, ASSESSMENT_YEAR) is not None:
        return

    version = questionnaire_repo.create_questionnaire_version(db, assessment_year=ASSESSMENT_YEAR, version_number=1)

    q1 = questionnaire_repo.add_question(
        db, version, key="has_other_income", order_index=1,
        question_type=enums.QuestionType.BOOLEAN, prompt="Do you have any other income sources?",
    )
    q2 = questionnaire_repo.add_question(
        db, version, key="other_income_count", order_index=2,
        question_type=enums.QuestionType.NUMBER, prompt="How many other income sources?",
    )
    q3 = questionnaire_repo.add_question(
        db, version, key="filing_intent", order_index=3,
        question_type=enums.QuestionType.SINGLE_CHOICE, prompt="How would you like to proceed?",
    )
    questionnaire_repo.add_question_option(db, q3, value="GUIDED", label="Guided walkthrough", order_index=1)
    questionnaire_repo.add_question_option(db, q3, value="QUICK", label="Quick estimate", order_index=2)
    q4 = questionnaire_repo.add_question(
        db, version, key="extra_details", order_index=4,
        question_type=enums.QuestionType.TEXT, prompt="Anything else you'd like to add?", is_required=False,
    )
    q5 = questionnaire_repo.add_question(
        db, version, key="confirm_ready", order_index=5,
        question_type=enums.QuestionType.BOOLEAN, prompt="Ready to see your summary?",
    )

    questionnaire_repo.add_question_rule(
        db, q1, action=enums.RuleAction.SKIP_QUESTION, condition_operator=enums.RuleConditionOperator.EQUALS,
        condition_value=False, target_question=q2, priority=0,
    )
    questionnaire_repo.add_question_rule(
        db, q3, action=enums.RuleAction.GO_TO_QUESTION, condition_operator=enums.RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q5, priority=0,
    )
    questionnaire_repo.add_question_rule(
        db, q3, action=enums.RuleAction.SKIP_QUESTION, condition_operator=enums.RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q4, priority=10,
    )

    db.refresh(version)
    questionnaire_repo.publish_questionnaire_version(db, version)


def main() -> None:
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        _ensure_mini_question_graph(db)

        email = f"e2e-seed-{uuid.uuid4()}@example.com"
        user = user_repo.create_user(db, UserCreate(email=email, password=SEED_PASSWORD))
        session = filing_session_repo.create_filing_session(
            db, FilingSessionCreate(user_id=user.id, assessment_year=ASSESSMENT_YEAR)
        )

        print(json.dumps({
            "email": email,
            "password": SEED_PASSWORD,
            "filing_session_id": str(session.id),
        }))
    finally:
        db.close()


if __name__ == "__main__":
    main()
