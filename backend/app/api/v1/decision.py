import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.decision import DecisionStateRead, FilingFlagRead
from app.services import decision as decision_service

router = APIRouter(prefix="/filing-sessions/{filing_session_id}", tags=["decision"])


@router.get("/decision-state", response_model=DecisionStateRead)
def get_decision_state(filing_session_id: uuid.UUID, db: Session = Depends(get_db)) -> DecisionStateRead:
    try:
        complexity, flags = decision_service.get_decision_state(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DecisionStateRead(
        complexity=complexity,
        flags=[FilingFlagRead.model_validate(f) for f in flags],
    )
