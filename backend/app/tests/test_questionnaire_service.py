import uuid

import pytest

from app.engines.questionnaire.errors import CrossQuestionnaireAnswerError
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.services import questionnaire as service


def _make_session(db_session, email):
    user = create_user(db_session, UserCreate(email=email))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def test_same_submission_is_idempotent(db_session, questionnaire_fixture):
    _version, questions = questionnaire_fixture
    session = _make_session(db_session, "idempotent@example.com")
    q1 = questions["has_other_income"]

    first = service.submit_answer(db_session, session.id, q1.id, True)
    second = service.submit_answer(db_session, session.id, q1.id, True)  # exact retry

    assert first.id == second.id
    history = service.questionnaire_repo.get_answer_history(db_session, session.id, q1.id)
    assert len(history) == 1  # no duplicate row was created


def test_changed_answer_creates_new_version(db_session, questionnaire_fixture):
    _version, questions = questionnaire_fixture
    session = _make_session(db_session, "changed@example.com")
    q1 = questions["has_other_income"]

    first = service.submit_answer(db_session, session.id, q1.id, True)
    second = service.submit_answer(db_session, session.id, q1.id, False)  # genuine change

    assert first.id != second.id
    assert second.supersedes_id == first.id
    history = service.questionnaire_repo.get_answer_history(db_session, session.id, q1.id)
    assert len(history) == 2
    assert history[0].is_current is False
    assert history[1].is_current is True


def test_cross_questionnaire_answer_rejected(db_session, questionnaire_fixture):
    from app.models.enums import QuestionType
    from app.repositories import questionnaire as repo

    _version, _questions = questionnaire_fixture
    session = _make_session(db_session, "cross@example.com")

    # A question from an entirely different (also published) questionnaire version.
    other_version = repo.create_questionnaire_version(db_session, assessment_year="2027-28", version_number=1)
    foreign_question = repo.add_question(
        db_session, other_version, key="foreign", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="from another year",
    )
    repo.publish_questionnaire_version(db_session, other_version)

    with pytest.raises(CrossQuestionnaireAnswerError):
        service.submit_answer(db_session, session.id, foreign_question.id, True)


def test_nonexistent_question_rejected_as_cross_questionnaire(db_session, questionnaire_fixture):
    _version, _questions = questionnaire_fixture
    session = _make_session(db_session, "missing@example.com")

    with pytest.raises(CrossQuestionnaireAnswerError):
        service.submit_answer(db_session, session.id, uuid.uuid4(), True)


def test_filing_session_binds_to_published_version_on_first_use(db_session, questionnaire_fixture):
    version, _questions = questionnaire_fixture
    session = _make_session(db_session, "binding@example.com")
    assert session.questionnaire_version_id is None

    service.get_current_question(db_session, session.id)

    db_session.refresh(session)
    assert session.questionnaire_version_id == version.id


def test_progress_is_backend_derived(db_session, questionnaire_fixture):
    _version, questions = questionnaire_fixture
    session = _make_session(db_session, "progress@example.com")

    progress = service.get_progress(db_session, session.id)
    assert progress["answered_questions"] == 0
    assert progress["is_complete"] is False

    service.submit_answer(db_session, session.id, questions["has_other_income"].id, True)
    progress = service.get_progress(db_session, session.id)
    assert progress["answered_questions"] == 1
