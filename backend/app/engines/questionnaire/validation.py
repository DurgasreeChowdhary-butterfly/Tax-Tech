from datetime import date
from decimal import Decimal, InvalidOperation

from app.engines.questionnaire.errors import InvalidAnswerError
from app.models.enums import QuestionType
from app.models.question import Question

_CURRENCY_MAX_DECIMALS = 2


def validate_answer_value(question: Question, value) -> None:
    """Validate a raw submitted answer value against the question's type/options.

    Raises InvalidAnswerError on any mismatch. Does not mutate anything —
    pure validation, called before an answer is ever persisted.
    """
    question_type = question.question_type

    if question_type in (QuestionType.INFORMATION, QuestionType.REVIEW_CARD, QuestionType.DOCUMENT_UPLOAD):
        # Out of scope this phase: INFORMATION/REVIEW_CARD carry no real answer
        # payload here, and DOCUMENT_UPLOAD belongs to the Phase 5/6 document
        # pipeline. Accept whatever is submitted without deeper validation.
        return

    if question_type == QuestionType.BOOLEAN:
        if not isinstance(value, bool):
            raise InvalidAnswerError(question.id, "expected a boolean value")
        return

    if question_type == QuestionType.TEXT:
        if not isinstance(value, str) or (question.is_required and not value.strip()):
            raise InvalidAnswerError(question.id, "expected a non-empty string")
        return

    if question_type == QuestionType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidAnswerError(question.id, "expected an integer value")
        return

    if question_type == QuestionType.CURRENCY:
        _validate_currency(question, value)
        return

    if question_type == QuestionType.DATE:
        if not isinstance(value, str):
            raise InvalidAnswerError(question.id, "expected an ISO date string (YYYY-MM-DD)")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise InvalidAnswerError(question.id, "expected an ISO date string (YYYY-MM-DD)") from exc
        return

    if question_type == QuestionType.SINGLE_CHOICE:
        _validate_single_choice(question, value)
        return

    if question_type == QuestionType.MULTI_CHOICE:
        _validate_multi_choice(question, value)
        return

    raise InvalidAnswerError(question.id, f"unsupported question type {question_type!r}")


def _validate_currency(question: Question, value) -> None:
    # Stored/validated as a decimal string, never a float, per the project's
    # Decimal-only rule for monetary values — even at raw capture time.
    if not isinstance(value, str):
        raise InvalidAnswerError(question.id, "expected a currency amount as a decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidAnswerError(question.id, "expected a currency amount as a decimal string") from exc
    if amount < 0:
        raise InvalidAnswerError(question.id, "currency amount must not be negative")
    exponent = amount.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < -_CURRENCY_MAX_DECIMALS:
        raise InvalidAnswerError(question.id, "currency amount must have at most 2 decimal places")


def _validate_single_choice(question: Question, value) -> None:
    if not isinstance(value, str):
        raise InvalidAnswerError(question.id, "expected a single option value (string)")
    valid_values = {option.value for option in question.options}
    if value not in valid_values:
        raise InvalidAnswerError(question.id, f"{value!r} is not a valid option")


def _validate_multi_choice(question: Question, value) -> None:
    if not isinstance(value, list) or not value:
        raise InvalidAnswerError(question.id, "expected a non-empty list of option values")
    if any(not isinstance(v, str) for v in value):
        raise InvalidAnswerError(question.id, "expected a list of option value strings")
    if len(set(value)) != len(value):
        raise InvalidAnswerError(question.id, "duplicate option values in answer")
    valid_values = {option.value for option in question.options}
    invalid = set(value) - valid_values
    if invalid:
        raise InvalidAnswerError(question.id, f"{sorted(invalid)!r} are not valid options")
