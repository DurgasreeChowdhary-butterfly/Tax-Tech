import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaxProfileCreate(BaseModel):
    user_id: uuid.UUID
    pan_encrypted: str | None = None


class TaxProfileUpdate(BaseModel):
    pan_encrypted: str | None = None


class TaxProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    pan_encrypted: str | None
    created_at: datetime
    updated_at: datetime
