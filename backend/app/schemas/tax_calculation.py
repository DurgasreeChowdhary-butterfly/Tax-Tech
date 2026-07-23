import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import TaxRegime


class CalculationLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_code: str
    sequence_index: int
    amount: Decimal
    step_metadata: dict | None


class TaxCalculationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    regime: TaxRegime
    calculation_engine_version: str
    gross_total_income: Decimal
    total_deductions_applied: Decimal
    taxable_income: Decimal
    tax_before_rebate: Decimal
    rebate_amount: Decimal
    tax_after_rebate: Decimal
    cess_amount: Decimal
    total_tax_liability: Decimal
    total_tds_credit: Decimal
    net_payable: Decimal
    created_at: datetime


class TaxCalculationResponse(BaseModel):
    calculation: TaxCalculationRead
    line_items: list[CalculationLineItemRead]
