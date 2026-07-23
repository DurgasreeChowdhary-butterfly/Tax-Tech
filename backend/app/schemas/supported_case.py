from pydantic import BaseModel

from app.models.enums import SupportedCaseOutcome


class SupportedCaseResultRead(BaseModel):
    outcome: SupportedCaseOutcome
    reasons: list[str]
