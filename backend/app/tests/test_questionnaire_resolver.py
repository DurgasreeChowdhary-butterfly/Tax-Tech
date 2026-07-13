import uuid

import pytest

from app.engines.questionnaire.errors import AmbiguousRoutingError
from app.engines.questionnaire.resolver import compute_progress, resolve_next_question
from app.models.enums import RuleAction, RuleConditionOperator
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.models.question_rule import QuestionRule


def _question(order_index: int) -> Question:
    q = Question(id=uuid.uuid4(), key=f"q{order_index}", order_index=order_index, prompt="p", is_required=True)
    return q


def _answer(question_id, value) -> QuestionAnswer:
    return QuestionAnswer(id=uuid.uuid4(), question_id=question_id, value=value, is_current=True)


def _rule(question_id, action, target_id=None, priority=0, operator=RuleConditionOperator.ALWAYS, value=None) -> QuestionRule:
    return QuestionRule(
        id=uuid.uuid4(),
        question_id=question_id,
        priority=priority,
        condition_operator=operator,
        condition_value=value,
        action=action,
        target_question_id=target_id,
    )


def test_linear_default_order_with_no_rules():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]

    assert resolve_next_question(questions, {}, {}) is q1
    answers = {q1.id: _answer(q1.id, True)}
    assert resolve_next_question(questions, {}, answers) is q2


def test_skip_question_behaviour():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]
    rules = {q1.id: [_rule(q1.id, RuleAction.SKIP_QUESTION, target_id=q2.id, operator=RuleConditionOperator.EQUALS, value=False)]}

    answers = {q1.id: _answer(q1.id, False)}
    assert resolve_next_question(questions, rules, answers) is q3  # q2 skipped


def test_go_to_question_behaviour():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]
    rules = {q1.id: [_rule(q1.id, RuleAction.GO_TO_QUESTION, target_id=q3.id, operator=RuleConditionOperator.EQUALS, value=True)]}

    answers = {q1.id: _answer(q1.id, True)}
    assert resolve_next_question(questions, rules, answers) is q3


def test_conditional_routing_only_fires_on_matching_condition():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]
    rules = {q1.id: [_rule(q1.id, RuleAction.GO_TO_QUESTION, target_id=q3.id, operator=RuleConditionOperator.EQUALS, value=True)]}

    answers = {q1.id: _answer(q1.id, False)}  # condition doesn't match
    assert resolve_next_question(questions, rules, answers) is q2  # normal order, no jump


def test_end_flow_behaviour():
    q1, q2 = _question(1), _question(2)
    questions = [q1, q2]
    rules = {q1.id: [_rule(q1.id, RuleAction.END_FLOW, operator=RuleConditionOperator.EQUALS, value=True)]}

    answers = {q1.id: _answer(q1.id, True)}
    assert resolve_next_question(questions, rules, answers) is None


def test_rule_priority_higher_precedence_wins():
    q1, q2 = _question(1), _question(2)
    questions = [q1, q2]
    rules = {
        q1.id: [
            _rule(q1.id, RuleAction.SKIP_QUESTION, target_id=q2.id, priority=0, operator=RuleConditionOperator.EQUALS, value=False),
            _rule(q1.id, RuleAction.SHOW_QUESTION, target_id=q2.id, priority=5, operator=RuleConditionOperator.EQUALS, value=False),
        ]
    }

    answers = {q1.id: _answer(q1.id, False)}
    # priority 0 (SKIP) beats priority 5 (SHOW) for the same target -> q2 skipped
    assert resolve_next_question(questions, rules, answers) is None


def test_conflicting_routing_at_same_priority_is_detected():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]
    rules = {
        q1.id: [
            _rule(q1.id, RuleAction.GO_TO_QUESTION, target_id=q2.id, priority=0, operator=RuleConditionOperator.EQUALS, value=True),
            _rule(q1.id, RuleAction.GO_TO_QUESTION, target_id=q3.id, priority=0, operator=RuleConditionOperator.EQUALS, value=True),
        ]
    }
    answers = {q1.id: _answer(q1.id, True)}

    with pytest.raises(AmbiguousRoutingError):
        resolve_next_question(questions, rules, answers)


def test_conflicting_visibility_at_same_priority_is_detected():
    q1, q2 = _question(1), _question(2)
    questions = [q1, q2]
    rules = {
        q1.id: [
            _rule(q1.id, RuleAction.SKIP_QUESTION, target_id=q2.id, priority=0, operator=RuleConditionOperator.EQUALS, value=True),
            _rule(q1.id, RuleAction.SHOW_QUESTION, target_id=q2.id, priority=0, operator=RuleConditionOperator.EQUALS, value=True),
        ]
    }
    answers = {q1.id: _answer(q1.id, True)}

    with pytest.raises(AmbiguousRoutingError):
        resolve_next_question(questions, rules, answers)


def test_backend_derived_progress():
    q1, q2, q3 = _question(1), _question(2), _question(3)
    questions = [q1, q2, q3]
    rules = {q1.id: [_rule(q1.id, RuleAction.SKIP_QUESTION, target_id=q2.id, operator=RuleConditionOperator.EQUALS, value=False)]}

    answers = {q1.id: _answer(q1.id, False)}
    progress = compute_progress(questions, rules, answers)
    # q2 is skipped, so only q1 and q3 are "applicable"; q1 answered, q3 not yet.
    assert progress == {"total_questions": 2, "answered_questions": 1, "is_complete": False}

    answers[q3.id] = _answer(q3.id, True)
    progress = compute_progress(questions, rules, answers)
    assert progress == {"total_questions": 2, "answered_questions": 2, "is_complete": True}
