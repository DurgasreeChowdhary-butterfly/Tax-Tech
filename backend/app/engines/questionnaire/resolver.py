import uuid
from dataclasses import dataclass, field

from app.engines.decision.conditions import condition_matches
from app.engines.questionnaire.errors import AmbiguousRoutingError
from app.models.enums import RuleAction
from app.models.question import Question
from app.models.question_answer import QuestionAnswer
from app.models.question_rule import QuestionRule

_NAVIGATION_ACTIONS = (RuleAction.GO_TO_QUESTION, RuleAction.END_FLOW)
_VISIBILITY_ACTIONS = (RuleAction.SKIP_QUESTION, RuleAction.SHOW_QUESTION)


@dataclass
class RoutingState:
    questions: list[Question]
    answers_by_question_id: dict[uuid.UUID, QuestionAnswer]
    skip_targets: set[uuid.UUID] = field(default_factory=set)
    nav_action: RuleAction | None = None
    nav_target_id: uuid.UUID | None = None

    @property
    def is_ended(self) -> bool:
        return self.nav_action == RuleAction.END_FLOW

    def applicable_questions(self) -> list[Question]:
        return [q for q in self.questions if q.id not in self.skip_targets]


def compute_routing_state(
    questions: list[Question],
    rules_by_question_id: dict[uuid.UUID, list[QuestionRule]],
    answers_by_question_id: dict[uuid.UUID, QuestionAnswer],
) -> RoutingState:
    """Deterministically compute skip-set + navigation outcome from answers so far.

    Questions are processed in ascending `order_index` (not answer timestamp),
    so the result depends only on the current set of answers, never on timing.
    Rules are evaluated in ascending priority; for a given (question, channel,
    target) the best (lowest-number) priority wins. Two matched rules for the
    same question at the *same* priority that disagree are ambiguous and raise.
    """
    state = RoutingState(questions=questions, answers_by_question_id=answers_by_question_id)
    show_targets: set[uuid.UUID] = set()
    nav_winner: QuestionRule | None = None

    for question in questions:
        answer = answers_by_question_id.get(question.id)
        if answer is None:
            continue

        matched = [r for r in rules_by_question_id.get(question.id, []) if condition_matches(r, answer.value)]
        if not matched:
            continue
        matched.sort(key=lambda r: r.priority)

        question_nav_winner: QuestionRule | None = None
        visibility_winners: dict[uuid.UUID, QuestionRule] = {}

        for rule in matched:
            if rule.action in _NAVIGATION_ACTIONS:
                if question_nav_winner is None:
                    question_nav_winner = rule
                elif rule.priority == question_nav_winner.priority:
                    if (rule.action, rule.target_question_id) != (
                        question_nav_winner.action,
                        question_nav_winner.target_question_id,
                    ):
                        raise AmbiguousRoutingError(
                            question.id,
                            f"conflicting navigation rules at priority {rule.priority}: "
                            f"{question_nav_winner.action} -> {question_nav_winner.target_question_id} vs "
                            f"{rule.action} -> {rule.target_question_id}",
                        )
                # else: strictly lower precedence, ignored
            elif rule.action in _VISIBILITY_ACTIONS:
                target_id = rule.target_question_id
                existing = visibility_winners.get(target_id)
                if existing is None:
                    visibility_winners[target_id] = rule
                elif existing.priority == rule.priority:
                    if existing.action != rule.action:
                        raise AmbiguousRoutingError(
                            question.id,
                            f"conflicting visibility rules at priority {rule.priority} for target "
                            f"{target_id}: {existing.action} vs {rule.action}",
                        )
                # else: strictly lower precedence, ignored
            # SET_PROFILE_FLAG / SET_COMPLEXITY / REQUIRE_REVIEW: matched but
            # inert in Phase 3 (Decision Engine territory — Phase 4).

        for target_id, rule in visibility_winners.items():
            if rule.action == RuleAction.SKIP_QUESTION:
                state.skip_targets.add(target_id)
                show_targets.discard(target_id)
            else:
                show_targets.add(target_id)
                state.skip_targets.discard(target_id)

        if question_nav_winner is not None:
            nav_winner = question_nav_winner  # later-answered question's nav decision supersedes an earlier one

    if nav_winner is not None:
        state.nav_action = nav_winner.action
        state.nav_target_id = nav_winner.target_question_id

    return state


def resolve_next_question(
    questions: list[Question],
    rules_by_question_id: dict[uuid.UUID, list[QuestionRule]],
    answers_by_question_id: dict[uuid.UUID, QuestionAnswer],
) -> Question | None:
    state = compute_routing_state(questions, rules_by_question_id, answers_by_question_id)

    if state.is_ended:
        return None

    if state.nav_action == RuleAction.GO_TO_QUESTION and state.nav_target_id is not None:
        target = next((q for q in questions if q.id == state.nav_target_id), None)
        if target is not None and target.id not in answers_by_question_id and target.id not in state.skip_targets:
            return target

    for question in questions:
        if question.id in answers_by_question_id:
            continue
        if question.id in state.skip_targets:
            continue
        return question

    return None


def compute_progress(
    questions: list[Question],
    rules_by_question_id: dict[uuid.UUID, list[QuestionRule]],
    answers_by_question_id: dict[uuid.UUID, QuestionAnswer],
) -> dict:
    state = compute_routing_state(questions, rules_by_question_id, answers_by_question_id)
    applicable = state.applicable_questions()
    answered = [q for q in applicable if q.id in answers_by_question_id]
    is_complete = state.is_ended or resolve_next_question(questions, rules_by_question_id, answers_by_question_id) is None
    return {
        "total_questions": len(applicable),
        "answered_questions": len(answered),
        "is_complete": is_complete,
    }
