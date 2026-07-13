import uuid

from app.engines.decision.errors import InvalidActionPayloadError
from app.models.enums import FilingComplexity, RuleAction


def validate_action_payload(question_id: uuid.UUID, action: RuleAction, action_payload) -> None:
    """Validate a rule's action_payload shape at rule-creation time (fixture/
    content-authoring time), so a malformed payload can never reach the
    decision engine at reconciliation time.
    """
    if action == RuleAction.SET_COMPLEXITY:
        complexity = (action_payload or {}).get("complexity") if isinstance(action_payload, dict) else None
        if complexity is None:
            raise InvalidActionPayloadError(question_id, "SET_COMPLEXITY requires action_payload={'complexity': <value>}")
        try:
            FilingComplexity(complexity)
        except ValueError as exc:
            raise InvalidActionPayloadError(question_id, f"{complexity!r} is not a valid complexity value") from exc

    elif action == RuleAction.SET_PROFILE_FLAG:
        flag = (action_payload or {}).get("flag") if isinstance(action_payload, dict) else None
        if not flag or not isinstance(flag, str):
            raise InvalidActionPayloadError(question_id, "SET_PROFILE_FLAG requires action_payload={'flag': <non-empty string>}")
