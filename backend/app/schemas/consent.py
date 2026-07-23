from datetime import datetime

from pydantic import BaseModel

from app.models.enums import UserConsentStatus


class ConsentStatusRead(BaseModel):
    code: str
    version_number: int
    title: str
    body_text: str
    is_required: bool
    status: UserConsentStatus | None
    recorded_at: datetime | None


class UserConsentRead(BaseModel):
    code: str
    version_number: int
    status: UserConsentStatus
    recorded_at: datetime
