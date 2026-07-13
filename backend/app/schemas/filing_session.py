import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FilerCategory, FilingComplexity, FilingSessionStatus, ResidencyStatus

ASSESSMENT_YEAR_PATTERN = r"^\d{4}-\d{2}$"


class FilingSessionCreate(BaseModel):
    user_id: uuid.UUID
    assessment_year: str = Field(pattern=ASSESSMENT_YEAR_PATTERN, examples=["2026-27"])


class FilingSessionUpdate(BaseModel):
    status: FilingSessionStatus | None = None
    complexity: FilingComplexity | None = None
    residency_status: ResidencyStatus | None = None
    filer_category: FilerCategory | None = None


class FilingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    assessment_year: str
    status: FilingSessionStatus
    complexity: FilingComplexity
    residency_status: ResidencyStatus | None
    filer_category: FilerCategory | None
    created_at: datetime
    updated_at: datetime
