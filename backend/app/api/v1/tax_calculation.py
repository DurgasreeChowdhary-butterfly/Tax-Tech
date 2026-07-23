import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.engines.tax.errors import (
    CaseNotSupportedForCalculationError,
    NoPublishedRuleSetError,
    SurchargeNotSupportedError,
)
from app.models.enums import TaxRegime
from app.models.filing_session import FilingSession
from app.schemas.tax_calculation import CalculationLineItemRead, TaxCalculationRead, TaxCalculationResponse
from app.services import tax_calculation as tax_calculation_service

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/calculations", tags=["tax"])


@router.get("/{regime}", response_model=TaxCalculationResponse)
def get_calculation(
    filing_session_id: uuid.UUID,
    regime: TaxRegime,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> TaxCalculationResponse:
    try:
        tax_calculation, line_items = tax_calculation_service.calculate_tax(db, filing_session_id, regime)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CaseNotSupportedForCalculationError, NoPublishedRuleSetError, SurchargeNotSupportedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return TaxCalculationResponse(
        calculation=TaxCalculationRead.model_validate(tax_calculation),
        line_items=[CalculationLineItemRead.model_validate(li) for li in line_items],
    )
