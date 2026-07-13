import uuid


class QuestionnaireError(Exception):
    """Base class for questionnaire engine domain errors."""


class NoPublishedVersionError(QuestionnaireError):
    def __init__(self, assessment_year: str):
        super().__init__(f"No published questionnaire version for assessment year {assessment_year!r}")
        self.assessment_year = assessment_year


class PublishedVersionImmutableError(QuestionnaireError):
    def __init__(self, version_id: uuid.UUID):
        super().__init__(f"Questionnaire version {version_id} is published and immutable")
        self.version_id = version_id


class InvalidRuleTargetError(QuestionnaireError):
    def __init__(self, target_question_id: uuid.UUID):
        super().__init__(f"Target question {target_question_id} does not belong to the same questionnaire version")
        self.target_question_id = target_question_id


class CrossQuestionnaireAnswerError(QuestionnaireError):
    def __init__(self, question_id: uuid.UUID, filing_session_id: uuid.UUID):
        super().__init__(
            f"Question {question_id} does not belong to filing session {filing_session_id}'s bound questionnaire version"
        )
        self.question_id = question_id
        self.filing_session_id = filing_session_id


class InvalidAnswerError(QuestionnaireError):
    def __init__(self, question_id: uuid.UUID, reason: str):
        super().__init__(f"Invalid answer for question {question_id}: {reason}")
        self.question_id = question_id
        self.reason = reason


class AmbiguousRoutingError(QuestionnaireError):
    def __init__(self, question_id: uuid.UUID, reason: str):
        super().__init__(f"Ambiguous routing decision triggered by question {question_id}: {reason}")
        self.question_id = question_id
        self.reason = reason


class EmptyQuestionnaireVersionError(QuestionnaireError):
    def __init__(self, version_id: uuid.UUID):
        super().__init__(f"Questionnaire version {version_id} has no questions and cannot be published")
        self.version_id = version_id
