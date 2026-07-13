import uuid

import pytest

from app.engines.decision.errors import ContradictoryDecisionError
from app.engines.decision.resolver import compute_decision_state
from app.models.enums import RuleAction, RuleConditionOperator
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.models.question_rule import QuestionRule


def _question(order_index: int) -> Question:
    return Question(id=uuid.uuid4(), key=f"q{order_index}", order_index=order_index, prompt="p", is_required=True)


def _answer(question_id, value) -> QuestionAnswer:
    return QuestionAnswer(id=uuid.uuid4(), question_id=question_id, value=value, is_current=True)


def _rule(question_id, action, priority=0, operator=RuleConditionOperator.EQUALS, value=True, payload=None) -> QuestionRule:
    return QuestionRule(
        id=uuid.uuid4(),
        question_id=question_id,
        priority=priority,
        condition_operator=operator,
        condition_value=value,
        action=action,
        action_payload=payload,
    )


def test_profile_flag_becomes_active_when_supporting_answer_matches():
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.SET_PROFILE_FLAG, payload={"flag": "FREELANCE_INCOME_DETECTED"})]}

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert state.active_flags == {"FREELANCE_INCOME_DETECTED"}

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, False)})
    assert state.active_flags == set()


def test_require_review_maps_to_review_required_flag():
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.REQUIRE_REVIEW)]}

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert state.active_flags == {"REVIEW_REQUIRED"}


def test_complexity_resolves_from_matching_rule():
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.SET_COMPLEXITY, payload={"complexity": "REVIEW_REQUIRED"})]}

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert state.complexity == "REVIEW_REQUIRED"

    state = compute_decision_state([q1], rules, {})  # unanswered -> no rule matches
    assert state.complexity is None


def test_complexity_shared_support_across_two_questions():
    q1, q2 = _question(1), _question(2)
    rules = {
        q1.id: [_rule(q1.id, RuleAction.SET_COMPLEXITY, payload={"complexity": "REVIEW_REQUIRED"})],
        q2.id: [_rule(q2.id, RuleAction.SET_COMPLEXITY, payload={"complexity": "REVIEW_REQUIRED"})],
    }
    answers = {q1.id: _answer(q1.id, True), q2.id: _answer(q2.id, True)}

    state = compute_decision_state([q1, q2], rules, answers)
    assert state.complexity == "REVIEW_REQUIRED"

    # Remove one supporting fact -> still supported by the other.
    state = compute_decision_state([q1, q2], rules, {q2.id: _answer(q2.id, True)})
    assert state.complexity == "REVIEW_REQUIRED"

    # Remove both -> reverts to no assertion.
    state = compute_decision_state([q1, q2], rules, {})
    assert state.complexity is None


def test_flag_shared_support_across_two_questions():
    q1, q2 = _question(1), _question(2)
    rules = {
        q1.id: [_rule(q1.id, RuleAction.REQUIRE_REVIEW)],
        q2.id: [_rule(q2.id, RuleAction.REQUIRE_REVIEW)],
    }

    both = {q1.id: _answer(q1.id, True), q2.id: _answer(q2.id, True)}
    assert compute_decision_state([q1, q2], rules, both).active_flags == {"REVIEW_REQUIRED"}

    only_q2 = {q1.id: _answer(q1.id, False), q2.id: _answer(q2.id, True)}
    assert compute_decision_state([q1, q2], rules, only_q2).active_flags == {"REVIEW_REQUIRED"}

    neither = {q1.id: _answer(q1.id, False), q2.id: _answer(q2.id, False)}
    assert compute_decision_state([q1, q2], rules, neither).active_flags == set()


def test_contradictory_complexity_at_same_priority_is_detected():
    q1 = _question(1)
    rules = {
        q1.id: [
            _rule(q1.id, RuleAction.SET_COMPLEXITY, priority=0, payload={"complexity": "REVIEW_REQUIRED"}),
            _rule(q1.id, RuleAction.SET_COMPLEXITY, priority=0, payload={"complexity": "NOT_SUPPORTED"}),
        ]
    }
    with pytest.raises(ContradictoryDecisionError):
        compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})


def test_lower_priority_complexity_rule_does_not_conflict():
    q1 = _question(1)
    rules = {
        q1.id: [
            _rule(q1.id, RuleAction.SET_COMPLEXITY, priority=0, payload={"complexity": "REVIEW_REQUIRED"}),
            _rule(q1.id, RuleAction.SET_COMPLEXITY, priority=5, payload={"complexity": "NOT_SUPPORTED"}),
        ]
    }
    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert state.complexity == "REVIEW_REQUIRED"  # priority 0 wins, priority 5 ignored, not a conflict


def test_known_flags_include_unsupported_ones():
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.SET_PROFILE_FLAG, payload={"flag": "FREELANCE_INCOME_DETECTED"})]}

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, False)})
    assert state.active_flags == set()
    assert state.known_flags == {"FREELANCE_INCOME_DETECTED"}


def test_require_review_alone_floors_complexity_to_review_required():
    """Regression: a REQUIRE_REVIEW match with no companion SET_COMPLEXITY
    rule must still elevate effective complexity, or a consumer that only
    checks filing_session.complexity could miss that review is required."""
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.REQUIRE_REVIEW)]}  # no SET_COMPLEXITY rule at all

    state = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert state.active_flags == {"REVIEW_REQUIRED"}
    assert state.complexity == "REVIEW_REQUIRED"


def test_require_review_does_not_downgrade_more_severe_complexity():
    q1, q2 = _question(1), _question(2)
    rules = {
        q1.id: [_rule(q1.id, RuleAction.REQUIRE_REVIEW)],
        q2.id: [_rule(q2.id, RuleAction.SET_COMPLEXITY, payload={"complexity": "NOT_SUPPORTED"})],
    }
    answers = {q1.id: _answer(q1.id, True), q2.id: _answer(q2.id, True)}

    state = compute_decision_state([q1, q2], rules, answers)
    assert state.complexity == "NOT_SUPPORTED"  # more severe than REVIEW_REQUIRED, not downgraded
    assert state.active_flags == {"REVIEW_REQUIRED"}


def test_require_review_removed_lets_complexity_revert():
    q1 = _question(1)
    rules = {q1.id: [_rule(q1.id, RuleAction.REQUIRE_REVIEW)]}

    active = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, True)})
    assert active.complexity == "REVIEW_REQUIRED"

    inactive = compute_decision_state([q1], rules, {q1.id: _answer(q1.id, False)})
    assert inactive.complexity is None
    assert inactive.active_flags == set()
