import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.engines.tax.errors import InvalidDeductionValueError, UnsupportedDeductionCodeError
from app.models.filing_session import FilingSession
from app.schemas.deduction import DeductionClaimRequest, DeductionRead
from app.services import deduction as deduction_service

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/deductions", tags=["tax"])


@router.post("", response_model=DeductionRead)
def claim_deduction(
    filing_session_id: uuid.UUID,
    body: DeductionClaimRequest,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DeductionRead:
    try:
        deduction = deduction_service.claim_deduction(db, filing_session_id, body.code, body.claimed_amount)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (UnsupportedDeductionCodeError, InvalidDeductionValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DeductionRead.model_validate(deduction)
