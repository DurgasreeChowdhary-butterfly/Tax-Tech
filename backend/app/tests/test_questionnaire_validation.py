import pytest

from app.engines.questionnaire.errors import InvalidAnswerError
from app.engines.questionnaire.validation import validate_answer_value


def test_boolean_answer_validation(questionnaire_fixture):
    _version, questions = questionnaire_fixture
    q1 = questions["has_other_income"]

    validate_answer_value(q1, True)
    validate_answer_value(q1, False)
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q1, "yes")


def test_number_answer_validation(questionnaire_fixture):
    _version, questions = questionnaire_fixture
    q2 = questions["other_income_count"]

    validate_answer_value(q2, 3)
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q2, 3.5)
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q2, "3")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q2, True)  # bool is a bool, not a NUMBER answer


def test_single_choice_answer_validation_against_options(questionnaire_fixture):
    _version, questions = questionnaire_fixture
    q3 = questions["filing_intent"]

    validate_answer_value(q3, "GUIDED")
    validate_answer_value(q3, "QUICK")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q3, "NOT_AN_OPTION")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q3, ["GUIDED"])  # wrong shape for SINGLE_CHOICE


def test_text_answer_validation(questionnaire_fixture):
    _version, questions = questionnaire_fixture
    q4 = questions["extra_details"]

    validate_answer_value(q4, "some notes")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q4, 123)


def test_currency_answer_validation_rejects_float_and_requires_decimal_string():
    from app.models.enums import QuestionType
    from app.models.question import Question

    q = Question(key="salary", order_index=1, question_type=QuestionType.CURRENCY, prompt="Salary?", is_required=True)

    validate_answer_value(q, "50000.00")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q, 50000.00)  # float is never acceptable for money
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q, "-5.00")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q, "5.001")


def test_date_answer_validation():
    from app.models.enums import QuestionType
    from app.models.question import Question

    q = Question(key="dob", order_index=1, question_type=QuestionType.DATE, prompt="DOB?", is_required=True)

    validate_answer_value(q, "1990-01-01")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q, "not-a-date")
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(q, "01/01/1990")


def test_multi_choice_answer_validation(questionnaire_fixture):
    from app.models.enums import QuestionType
    from app.models.question_option import QuestionOption

    _version, questions = questionnaire_fixture
    q3 = questions["filing_intent"]
    # Reuse q3's options but exercise MULTI_CHOICE semantics by constructing a
    # standalone in-memory question with the same option set.
    multi = type(q3)(
        key="multi", order_index=1, question_type=QuestionType.MULTI_CHOICE, prompt="pick any", is_required=True
    )
    multi.options = [
        QuestionOption(value="GUIDED", label="Guided", order_index=1),
        QuestionOption(value="QUICK", label="Quick", order_index=2),
    ]

    validate_answer_value(multi, ["GUIDED", "QUICK"])
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(multi, [])
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(multi, ["GUIDED", "GUIDED"])
    with pytest.raises(InvalidAnswerError):
        validate_answer_value(multi, ["NOT_VALID"])
