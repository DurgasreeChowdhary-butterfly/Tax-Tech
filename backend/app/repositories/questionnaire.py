import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.engines.decision.lifecycle import validate_action_payload
from app.engines.questionnaire.lifecycle import validate_draft, validate_publishable, validate_rule_target
from app.models.enums import QuestionnaireVersionStatus, RuleAction, RuleConditionOperator
from app.models.filing_session import FilingSession
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.models.question_option import QuestionOption
from app.models.question_rule import QuestionRule
from app.models.questionnaire_version import QuestionnaireVersion


def create_questionnaire_version(db: Session, assessment_year: str, version_number: int) -> QuestionnaireVersion:
    version = QuestionnaireVersion(assessment_year=assessment_year, version_number=version_number)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def add_question(
    db: Session,
    version: QuestionnaireVersion,
    *,
    key: str,
    order_index: int,
    question_type,
    prompt: str,
    is_required: bool = True,
) -> Question:
    validate_draft(version)
    question = Question(
        questionnaire_version_id=version.id,
        key=key,
        order_index=order_index,
        question_type=question_type,
        prompt=prompt,
        is_required=is_required,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def add_question_option(db: Session, question: Question, *, value: str, label: str, order_index: int) -> QuestionOption:
    validate_draft(question.questionnaire_version)
    option = QuestionOption(
        question_id=question.id,
        questionnaire_version_id=question.questionnaire_version_id,
        value=value,
        label=label,
        order_index=order_index,
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def add_question_rule(
    db: Session,
    question: Question,
    *,
    action: RuleAction,
    condition_operator: RuleConditionOperator = RuleConditionOperator.ALWAYS,
    condition_value=None,
    target_question: Question | None = None,
    action_payload=None,
    priority: int = 0,
) -> QuestionRule:
    validate_draft(question.questionnaire_version)
    validate_rule_target(question, target_question)
    validate_action_payload(question.id, action, action_payload)
    rule = QuestionRule(
        questionnaire_version_id=question.questionnaire_version_id,
        question_id=question.id,
        priority=priority,
        condition_operator=condition_operator,
        condition_value=condition_value,
        action=action,
        target_question_id=target_question.id if target_question else None,
        action_payload=action_payload,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def publish_questionnaire_version(db: Session, version: QuestionnaireVersion) -> QuestionnaireVersion:
    validate_publishable(version)
    version.status = QuestionnaireVersionStatus.PUBLISHED
    version.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return version


def get_published_version_for_assessment_year(db: Session, assessment_year: str) -> QuestionnaireVersion | None:
    stmt = (
        select(QuestionnaireVersion)
        .where(
            QuestionnaireVersion.assessment_year == assessment_year,
            QuestionnaireVersion.status == QuestionnaireVersionStatus.PUBLISHED,
        )
        .order_by(QuestionnaireVersion.version_number.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def get_version_by_id(db: Session, version_id: uuid.UUID) -> QuestionnaireVersion | None:
    return db.get(QuestionnaireVersion, version_id)


def bind_filing_session_version(db: Session, filing_session: FilingSession, version: QuestionnaireVersion) -> FilingSession:
    if filing_session.questionnaire_version_id is None:
        filing_session.questionnaire_version_id = version.id
        db.commit()
        db.refresh(filing_session)
    return filing_session


def get_questions_for_version(db: Session, version_id: uuid.UUID) -> list[Question]:
    stmt = select(Question).where(Question.questionnaire_version_id == version_id).order_by(Question.order_index)
    return list(db.execute(stmt).scalars().all())


def get_question_by_id(db: Session, question_id: uuid.UUID) -> Question | None:
    return db.get(Question, question_id)


def get_rules_for_version(db: Session, version_id: uuid.UUID) -> list[QuestionRule]:
    stmt = select(QuestionRule).where(QuestionRule.questionnaire_version_id == version_id)
    return list(db.execute(stmt).scalars().all())


def get_current_answers_for_session(db: Session, filing_session_id: uuid.UUID) -> dict[uuid.UUID, QuestionAnswer]:
    stmt = select(QuestionAnswer).where(
        QuestionAnswer.filing_session_id == filing_session_id, QuestionAnswer.is_current.is_(True)
    )
    return {answer.question_id: answer for answer in db.execute(stmt).scalars().all()}


def get_current_answer(db: Session, filing_session_id: uuid.UUID, question_id: uuid.UUID) -> QuestionAnswer | None:
    stmt = select(QuestionAnswer).where(
        QuestionAnswer.filing_session_id == filing_session_id,
        QuestionAnswer.question_id == question_id,
        QuestionAnswer.is_current.is_(True),
    )
    return db.execute(stmt).scalars().first()


def get_answer_history(db: Session, filing_session_id: uuid.UUID, question_id: uuid.UUID) -> list[QuestionAnswer]:
    stmt = (
        select(QuestionAnswer)
        .where(QuestionAnswer.filing_session_id == filing_session_id, QuestionAnswer.question_id == question_id)
        .order_by(QuestionAnswer.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def record_answer(
    db: Session,
    *,
    filing_session_id: uuid.UUID,
    question_id: uuid.UUID,
    questionnaire_version_id: uuid.UUID,
    value,
) -> QuestionAnswer:
    """Create a new current answer version, idempotently.

    If the submitted value is identical to the existing current answer, no new
    row is created (safe for exact-retry mobile network behaviour). Otherwise a
    new row is inserted and the previous current row is flipped non-current in
    the same transaction. A concurrent duplicate submission that races past the
    idempotency check is caught by the partial unique index and reconciled here
    rather than surfaced as a spurious error.
    """
    current = get_current_answer(db, filing_session_id, question_id)
    if current is not None and current.value == value:
        return current

    new_answer = QuestionAnswer(
        filing_session_id=filing_session_id,
        question_id=question_id,
        questionnaire_version_id=questionnaire_version_id,
        value=value,
        is_current=True,
        supersedes_id=current.id if current else None,
    )
    if current is not None:
        current.is_current = False
    db.add(new_answer)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        reconciled = get_current_answer(db, filing_session_id, question_id)
        if reconciled is not None and reconciled.value == value:
            return reconciled
        raise

    db.refresh(new_answer)
    return new_answer
