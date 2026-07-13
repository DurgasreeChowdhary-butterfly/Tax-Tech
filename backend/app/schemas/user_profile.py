import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserProfileCreate(BaseModel):
    user_id: uuid.UUID
    full_name: str | None = None
    date_of_birth: date | None = None
    contact_number: str | None = None


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: date | None = None
    contact_number: str | None = None


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str | None
    date_of_birth: date | None
    contact_number: str | None
    created_at: datetime
    updated_at: datetime
