import uuid

from sqlalchemy.orm import Session

from app.engines.questionnaire.errors import CrossQuestionnaireAnswerError, NoPublishedVersionError
from app.engines.questionnaire.resolver import compute_progress, resolve_next_question
from app.engines.questionnaire.validation import validate_answer_value
from app.models.filing_session import FilingSession
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.repositories import questionnaire as questionnaire_repo
from app.repositories.filing_session import get_filing_session


def get_filing_session_or_raise(db: Session, filing_session_id: uuid.UUID) -> FilingSession:
    filing_session = get_filing_session(db, filing_session_id)
    if filing_session is None:
        raise ValueError(f"Filing session {filing_session_id} not found")
    return filing_session


def ensure_bound_version(db: Session, filing_session: FilingSession):
    if filing_session.questionnaire_version_id is not None:
        return questionnaire_repo.get_version_by_id(db, filing_session.questionnaire_version_id)

    version = questionnaire_repo.get_published_version_for_assessment_year(db, filing_session.assessment_year)
    if version is None:
        raise NoPublishedVersionError(filing_session.assessment_year)
    questionnaire_repo.bind_filing_session_version(db, filing_session, version)
    return version


def load_routing_inputs(db: Session, filing_session: FilingSession, version):
    """Shared by the questionnaire and decision engines/services: everything
    needed to deterministically resolve routing or decision state from the
    current answer set."""
    questions = questionnaire_repo.get_questions_for_version(db, version.id)
    rules = questionnaire_repo.get_rules_for_version(db, version.id)
    rules_by_question_id: dict[uuid.UUID, list] = {}
    for rule in rules:
        rules_by_question_id.setdefault(rule.question_id, []).append(rule)
    answers_by_question_id = questionnaire_repo.get_current_answers_for_session(db, filing_session.id)
    return questions, rules_by_question_id, answers_by_question_id


def get_current_question(db: Session, filing_session_id: uuid.UUID) -> Question | None:
    filing_session = get_filing_session_or_raise(db, filing_session_id)
    version = ensure_bound_version(db, filing_session)
    questions, rules_by_question_id, answers_by_question_id = load_routing_inputs(db, filing_session, version)
    return resolve_next_question(questions, rules_by_question_id, answers_by_question_id)


def get_progress(db: Session, filing_session_id: uuid.UUID) -> dict:
    filing_session = get_filing_session_or_raise(db, filing_session_id)
    version = ensure_bound_version(db, filing_session)
    questions, rules_by_question_id, answers_by_question_id = load_routing_inputs(db, filing_session, version)
    return compute_progress(questions, rules_by_question_id, answers_by_question_id)


def submit_answer(db: Session, filing_session_id: uuid.UUID, question_id: uuid.UUID, value) -> QuestionAnswer:
    from app.services import decision as decision_service

    filing_session = get_filing_session_or_raise(db, filing_session_id)
    version = ensure_bound_version(db, filing_session)

    question = questionnaire_repo.get_question_by_id(db, question_id)
    if question is None or question.questionnaire_version_id != version.id:
        raise CrossQuestionnaireAnswerError(question_id, filing_session_id)

    validate_answer_value(question, value)

    answer = questionnaire_repo.record_answer(
        db,
        filing_session_id=filing_session.id,
        question_id=question.id,
        questionnaire_version_id=version.id,
        value=value,
    )

    # Reconcile decision state (flags/complexity) against the now-current
    # answer set. Runs on every submission, including idempotent retries and
    # reverted answers, so stale effects never linger.
    decision_service.reconcile_decision_state(db, filing_session_id)

    return answer
