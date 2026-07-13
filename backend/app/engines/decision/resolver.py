import uuid
from dataclasses import dataclass, field

from app.engines.decision.conditions import condition_matches
from app.engines.decision.errors import ContradictoryDecisionError
from app.models.enums import FilingComplexity, RuleAction
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.models.question_rule import QuestionRule

REVIEW_REQUIRED_FLAG = "REVIEW_REQUIRED"

# Severity order for reconciling REQUIRE_REVIEW against SET_COMPLEXITY: a
# REQUIRE_REVIEW match must never leave complexity looking less severe than
# REVIEW_REQUIRED, or a consumer that only checks filing_session.complexity
# (the obvious, most-likely-checked field) could silently miss that review is
# required. NOT_SUPPORTED, being more severe, is never downgraded by this floor.
_COMPLEXITY_SEVERITY = {
    None: 0,
    FilingComplexity.UNDETERMINED.value: 0,
    FilingComplexity.SIMPLE.value: 1,
    FilingComplexity.REVIEW_REQUIRED.value: 2,
    FilingComplexity.NOT_SUPPORTED.value: 3,
}


@dataclass
class DecisionState:
    """Effective decision state as a pure function of current answers + rules.

    Recomputed from scratch on every reconciliation — never patched
    incrementally — so a changed or reverted answer is always fully reflected,
    including cases where a flag/complexity is supported by more than one
    currently-true fact (shared support).
    """

    complexity: str | None  # a FilingComplexity value, or None meaning "no rule currently asserts one"
    active_flags: set[str] = field(default_factory=set)
    known_flags: set[str] = field(default_factory=set)  # every flag_code any rule in this version could ever emit


def compute_decision_state(
    questions: list[Question],
    rules_by_question_id: dict[uuid.UUID, list[QuestionRule]],
    answers_by_question_id: dict[uuid.UUID, QuestionAnswer],
) -> DecisionState:
    complexity_rules: list[QuestionRule] = []
    flags_with_support: dict[str, list[QuestionRule]] = {}
    known_flags: set[str] = set()

    for rules in rules_by_question_id.values():
        for rule in rules:
            code = _flag_code_for_rule(rule)
            if code is not None:
                known_flags.add(code)

    for question in questions:  # ascending order_index: deterministic, independent of answer timing
        answer = answers_by_question_id.get(question.id)
        if answer is None:
            continue
        for rule in rules_by_question_id.get(question.id, []):
            if not condition_matches(rule, answer.value):
                continue
            if rule.action == RuleAction.SET_COMPLEXITY:
                complexity_rules.append(rule)
            else:
                code = _flag_code_for_rule(rule)
                if code is not None:
                    flags_with_support.setdefault(code, []).append(rule)

    complexity = _resolve_complexity(complexity_rules)
    active_flags = set(flags_with_support.keys())

    if REVIEW_REQUIRED_FLAG in active_flags and _COMPLEXITY_SEVERITY[complexity] < _COMPLEXITY_SEVERITY[FilingComplexity.REVIEW_REQUIRED.value]:
        # A currently-active REQUIRE_REVIEW (or an explicit SET_PROFILE_FLAG
        # named REVIEW_REQUIRED) must never be silently invisible to a
        # consumer that only inspects complexity — it can only be overridden
        # by a MORE severe explicit SET_COMPLEXITY (e.g. NOT_SUPPORTED).
        complexity = FilingComplexity.REVIEW_REQUIRED.value

    return DecisionState(complexity=complexity, active_flags=active_flags, known_flags=known_flags)


def _flag_code_for_rule(rule: QuestionRule) -> str | None:
    if rule.action == RuleAction.SET_PROFILE_FLAG:
        payload = rule.action_payload or {}
        return payload.get("flag")
    if rule.action == RuleAction.REQUIRE_REVIEW:
        return REVIEW_REQUIRED_FLAG
    return None


def _resolve_complexity(rules: list[QuestionRule]) -> str | None:
    if not rules:
        return None
    rules_sorted = sorted(rules, key=lambda r: r.priority)
    best_priority = rules_sorted[0].priority
    top_tier = [r for r in rules_sorted if r.priority == best_priority]
    values = {(r.action_payload or {}).get("complexity") for r in top_tier}
    if len(values) > 1:
        raise ContradictoryDecisionError(
            f"conflicting SET_COMPLEXITY rules at priority {best_priority}: {sorted(v for v in values if v)}"
        )
    return next(iter(values))
