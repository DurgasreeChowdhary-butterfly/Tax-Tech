import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str
    # Raw password, in memory only for the duration of the request — hashed
    # immediately in app.repositories.user.create_user (bcrypt, see
    # app/core/security.py) and never persisted or logged in this form.
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    email: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime
    updated_at: datetime
