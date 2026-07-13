from app.engines.questionnaire.errors import (
    EmptyQuestionnaireVersionError,
    InvalidRuleTargetError,
    PublishedVersionImmutableError,
)
from app.models.enums import QuestionnaireVersionStatus
from app.models.question import Question
from app.models.questionnaire_version import QuestionnaireVersion


def validate_rule_target(question: Question, target_question: Question | None) -> None:
    """A rule's target question, if any, must belong to the same questionnaire version."""
    if target_question is None:
        return
    if target_question.questionnaire_version_id != question.questionnaire_version_id:
        raise InvalidRuleTargetError(target_question.id)


def validate_publishable(version: QuestionnaireVersion) -> None:
    if version.status == QuestionnaireVersionStatus.PUBLISHED:
        raise PublishedVersionImmutableError(version.id)
    if not version.questions:
        raise EmptyQuestionnaireVersionError(version.id)


def validate_draft(version: QuestionnaireVersion) -> None:
    """Guard for any write to a version's questions/options/rules."""
    if version.status == QuestionnaireVersionStatus.PUBLISHED:
        raise PublishedVersionImmutableError(version.id)
