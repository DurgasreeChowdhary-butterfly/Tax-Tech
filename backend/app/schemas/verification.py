import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import VerificationAction


class VerifyFieldRequest(BaseModel):
    action: VerificationAction
    value: Any = None  # required for CORRECT; ignored for CONFIRM


class ExtractedFieldVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: VerificationAction
    verified_value: Any
    is_current: bool
    created_at: datetime


class ReviewFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_name: str
    raw_value: Any
    confidence: float
    is_supported: bool
    current_verification: ExtractedFieldVerificationRead | None


class SalaryIncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_extraction_id: uuid.UUID
    employer_name: str | None
    gross_salary: Decimal | None
    tds_deducted: Decimal | None
    updated_at: datetime


class InterestIncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_extraction_id: uuid.UUID
    interest_amount: Decimal | None
    updated_at: datetime


class VerifyFieldResponse(BaseModel):
    verification: ExtractedFieldVerificationRead
    salary_income: SalaryIncomeRead | None = None
    interest_income: InterestIncomeRead | None = None
