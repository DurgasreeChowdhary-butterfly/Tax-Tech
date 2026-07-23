import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.models.filing_session import FilingSession
from app.schemas.supported_case import SupportedCaseResultRead
from app.services import supported_case as supported_case_service

router = APIRouter(prefix="/filing-sessions/{filing_session_id}", tags=["tax"])


@router.get("/supported-case", response_model=SupportedCaseResultRead)
def get_supported_case(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> SupportedCaseResultRead:
    try:
        result = supported_case_service.evaluate_filing_session(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SupportedCaseResultRead(outcome=result.outcome, reasons=list(result.reasons))
