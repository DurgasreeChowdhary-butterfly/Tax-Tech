from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DeductionClaimRequest(BaseModel):
    code: str
    claimed_amount: str


class DeductionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    claimed_amount: Decimal
    updated_at: datetime
