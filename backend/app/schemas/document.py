import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    deleted_at: datetime | None


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    is_duplicate: bool


class DocumentListResponse(BaseModel):
    documents: list[DocumentRead]
