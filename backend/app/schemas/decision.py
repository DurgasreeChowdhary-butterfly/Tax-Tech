from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FilingComplexity


class FilingFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    flag_code: str
    is_active: bool
    updated_at: datetime


class DecisionStateRead(BaseModel):
    complexity: FilingComplexity
    flags: list[FilingFlagRead]
