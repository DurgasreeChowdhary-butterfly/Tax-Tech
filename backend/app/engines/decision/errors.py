import uuid


class DecisionError(Exception):
    """Base class for decision engine domain errors."""


class ContradictoryDecisionError(DecisionError):
    def __init__(self, reason: str):
        super().__init__(f"Contradictory decision rules: {reason}")
        self.reason = reason


class InvalidActionPayloadError(DecisionError):
    def __init__(self, question_id: uuid.UUID, reason: str):
        super().__init__(f"Invalid action payload for rule on question {question_id}: {reason}")
        self.question_id = question_id
        self.reason = reason
