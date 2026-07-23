import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from app.engines.extraction.failure_classification import safe_message_for
from app.models.enums import DocumentProcessingJobStatus, ExtractionFailureCode, ExtractionProviderName


class DocumentProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tax_document_id: uuid.UUID
    provider: ExtractionProviderName
    status: DocumentProcessingJobStatus
    error_code: ExtractionFailureCode | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def error_message(self) -> str | None:
        # Derived from the fixed, safe error_code only — never the raw
        # internal error_detail (which may contain storage keys, exception
        # text, etc. and is never exposed via any API schema).
        return safe_message_for(self.error_code) if self.error_code else None


class ExtractedFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_name: str
    raw_value: Any
    confidence: float


class DocumentExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: ExtractionProviderName
    provider_version: str
    created_at: datetime
    fields: list[ExtractedFieldRead]
