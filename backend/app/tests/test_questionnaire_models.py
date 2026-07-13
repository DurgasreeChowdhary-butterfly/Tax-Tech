import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.engines.questionnaire.errors import InvalidRuleTargetError, PublishedVersionImmutableError
from app.models.enums import QuestionnaireVersionStatus, QuestionType, RuleAction, RuleConditionOperator
from app.models.question_answer import QuestionAnswer
from app.repositories import questionnaire as repo


def test_questionnaire_version_relationships(questionnaire_fixture):
    version, questions = questionnaire_fixture

    assert version.status == QuestionnaireVersionStatus.PUBLISHED
    assert len(version.questions) == 5
    assert {q.key for q in version.questions} == set(questions.keys())

    q3 = questions["filing_intent"]
    assert q3.questionnaire_version.id == version.id
    assert {o.value for o in q3.options} == {"GUIDED", "QUICK"}


def test_published_version_rejects_new_questions(db_session, questionnaire_fixture):
    version, _questions = questionnaire_fixture

    with pytest.raises(PublishedVersionImmutableError):
        repo.add_question(
            db_session, version, key="late_addition", order_index=99,
            question_type=QuestionType.TEXT, prompt="too late",
        )


def test_published_version_rejects_republish(db_session, questionnaire_fixture):
    version, _questions = questionnaire_fixture

    with pytest.raises(PublishedVersionImmutableError):
        repo.publish_questionnaire_version(db_session, version)


def test_invalid_rule_target_rejected_across_versions(db_session, questionnaire_fixture):
    _version, questions = questionnaire_fixture

    other_version = repo.create_questionnaire_version(db_session, assessment_year="2027-28", version_number=1)
    foreign_question = repo.add_question(
        db_session, other_version, key="foreign", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="from another version",
    )

    draft_version = repo.create_questionnaire_version(db_session, assessment_year="2028-29", version_number=1)
    q1 = repo.add_question(
        db_session, draft_version, key="q1", order_index=1, question_type=QuestionType.BOOLEAN, prompt="q1"
    )

    with pytest.raises(InvalidRuleTargetError):
        repo.add_question_rule(
            db_session, q1, action=RuleAction.SKIP_QUESTION, condition_operator=RuleConditionOperator.ALWAYS,
            target_question=foreign_question,
        )


def test_answer_history_is_immutable_append_only(db_session, questionnaire_fixture):
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate

    version, questions = questionnaire_fixture
    user = create_user(db_session, UserCreate(email="history@example.com"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    q1 = questions["has_other_income"]
    first = repo.record_answer(
        db_session, filing_session_id=session.id, question_id=q1.id, questionnaire_version_id=version.id, value=True
    )
    second = repo.record_answer(
        db_session, filing_session_id=session.id, question_id=q1.id, questionnaire_version_id=version.id, value=False
    )

    history = repo.get_answer_history(db_session, session.id, q1.id)
    assert [row.id for row in history] == [first.id, second.id]

    db_session.refresh(first)
    assert first.is_current is False
    assert second.is_current is True
    assert second.supersedes_id == first.id
    # The original row's own fields were never rewritten.
    assert first.value is True


def test_exactly_one_current_answer_enforced_at_db_level(db_session, questionnaire_fixture):
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate

    version, questions = questionnaire_fixture
    user = create_user(db_session, UserCreate(email="dbinvariant@example.com"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    q1 = questions["has_other_income"]

    repo.record_answer(
        db_session, filing_session_id=session.id, question_id=q1.id, questionnaire_version_id=version.id, value=True
    )

    # Bypass the service/repository idempotency guard entirely and attempt to
    # insert a second "current" row directly — the partial unique index (not
    # just Python logic) must reject this.
    duplicate = QuestionAnswer(
        id=uuid.uuid4(),
        filing_session_id=session.id,
        question_id=q1.id,
        questionnaire_version_id=version.id,
        value=False,
        is_current=True,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
