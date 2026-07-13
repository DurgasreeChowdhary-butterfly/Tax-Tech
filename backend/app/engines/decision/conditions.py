from app.models.enums import RuleConditionOperator
from app.models.question_rule import QuestionRule


def condition_matches(rule: QuestionRule, answer_value) -> bool:
    """Shared by the questionnaire (routing) and decision engines: does this
    rule's condition match the given current answer value?
    """
    if rule.condition_operator == RuleConditionOperator.ALWAYS:
        return True
    if rule.condition_operator == RuleConditionOperator.EQUALS:
        return answer_value == rule.condition_value
    if rule.condition_operator == RuleConditionOperator.NOT_EQUALS:
        return answer_value != rule.condition_value
    if rule.condition_operator == RuleConditionOperator.IN:
        return isinstance(rule.condition_value, list) and answer_value in rule.condition_value
    raise ValueError(f"unsupported condition operator {rule.condition_operator!r}")
