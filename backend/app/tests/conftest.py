import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers all models on Base.metadata)
from app.core.database import Base


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def questionnaire_fixture(db_session):
    """Builds and publishes a small, deterministic 5-question graph.

    Q1 has_other_income (BOOLEAN)   -> if false, SKIP Q2
    Q2 other_income_count (NUMBER)
    Q3 filing_intent (SINGLE_CHOICE: GUIDED/QUICK) -> if QUICK, GOTO Q5 (and SKIP Q4 as a fallback)
    Q4 extra_details (TEXT, optional)
    Q5 confirm_ready (BOOLEAN)

    Returns (version, questions) where `questions` maps key -> Question.
    """
    from app.models.enums import QuestionType, RuleAction, RuleConditionOperator
    from app.repositories import questionnaire as repo

    version = repo.create_questionnaire_version(db_session, assessment_year="2026-27", version_number=1)

    q1 = repo.add_question(
        db_session, version, key="has_other_income", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="Do you have any other income sources?",
    )
    q2 = repo.add_question(
        db_session, version, key="other_income_count", order_index=2,
        question_type=QuestionType.NUMBER, prompt="How many other income sources?",
    )
    q3 = repo.add_question(
        db_session, version, key="filing_intent", order_index=3,
        question_type=QuestionType.SINGLE_CHOICE, prompt="How would you like to proceed?",
    )
    repo.add_question_option(db_session, q3, value="GUIDED", label="Guided walkthrough", order_index=1)
    repo.add_question_option(db_session, q3, value="QUICK", label="Quick estimate", order_index=2)
    q4 = repo.add_question(
        db_session, version, key="extra_details", order_index=4,
        question_type=QuestionType.TEXT, prompt="Anything else you'd like to add?", is_required=False,
    )
    q5 = repo.add_question(
        db_session, version, key="confirm_ready", order_index=5,
        question_type=QuestionType.BOOLEAN, prompt="Ready to see your summary?",
    )

    repo.add_question_rule(
        db_session, q1, action=RuleAction.SKIP_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=False, target_question=q2, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.GO_TO_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q5, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.SKIP_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q4, priority=10,
    )

    db_session.refresh(version)
    repo.publish_questionnaire_version(db_session, version)

    questions = {"has_other_income": q1, "other_income_count": q2, "filing_intent": q3, "extra_details": q4, "confirm_ready": q5}
    return version, questions


@pytest.fixture()
def decision_fixture(db_session):
    """Builds and publishes a small graph exercising all Phase 4 decision actions.

    Q1 has_freelance_income (BOOLEAN) -> true: SET_PROFILE_FLAG(FREELANCE_INCOME_DETECTED)
                                          true: SET_COMPLEXITY(REVIEW_REQUIRED)
    Q2 has_crypto_income (BOOLEAN)    -> true: SET_COMPLEXITY(REVIEW_REQUIRED)  [shared support with Q1 for complexity]
                                          true: REQUIRE_REVIEW
    Q3 has_other_review_trigger (BOOLEAN) -> true: REQUIRE_REVIEW  [shared support with Q2 for REVIEW_REQUIRED flag]
    Q4 confirm_end (BOOLEAN)         -> true: END_FLOW

    Returns (version, questions) where `questions` maps key -> Question.
    """
    from app.models.enums import FilingComplexity, QuestionType, RuleAction, RuleConditionOperator
    from app.repositories import questionnaire as repo

    version = repo.create_questionnaire_version(db_session, assessment_year="2026-27", version_number=1)

    q1 = repo.add_question(
        db_session, version, key="has_freelance_income", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="Do you have freelance income?",
    )
    q2 = repo.add_question(
        db_session, version, key="has_crypto_income", order_index=2,
        question_type=QuestionType.BOOLEAN, prompt="Do you have crypto income?",
    )
    q3 = repo.add_question(
        db_session, version, key="has_other_review_trigger", order_index=3,
        question_type=QuestionType.BOOLEAN, prompt="Any other reason you think you need review?",
    )
    q4 = repo.add_question(
        db_session, version, key="confirm_end", order_index=4,
        question_type=QuestionType.BOOLEAN, prompt="Stop here?",
    )

    repo.add_question_rule(
        db_session, q1, action=RuleAction.SET_PROFILE_FLAG, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"flag": "FREELANCE_INCOME_DETECTED"}, priority=0,
    )
    repo.add_question_rule(
        db_session, q1, action=RuleAction.SET_COMPLEXITY, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"complexity": FilingComplexity.REVIEW_REQUIRED.value}, priority=0,
    )
    repo.add_question_rule(
        db_session, q2, action=RuleAction.SET_COMPLEXITY, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"complexity": FilingComplexity.REVIEW_REQUIRED.value}, priority=0,
    )
    repo.add_question_rule(
        db_session, q2, action=RuleAction.REQUIRE_REVIEW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.REQUIRE_REVIEW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )
    repo.add_question_rule(
        db_session, q4, action=RuleAction.END_FLOW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )

    db_session.refresh(version)
    repo.publish_questionnaire_version(db_session, version)

    questions = {
        "has_freelance_income": q1,
        "has_crypto_income": q2,
        "has_other_review_trigger": q3,
        "confirm_end": q4,
    }
    return version, questions
