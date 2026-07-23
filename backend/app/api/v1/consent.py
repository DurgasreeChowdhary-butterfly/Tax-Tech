import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.models.filing_session import FilingSession
from app.schemas.consent import ConsentStatusRead, UserConsentRead
from app.services import consent as consent_service
from app.services.consent_errors import (
    ConsentDefinitionNotFoundError,
    NoActiveConsentToWithdrawError,
)

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/consents", tags=["consent"])


@router.get("", response_model=list[ConsentStatusRead])
def get_consent_status(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> list[ConsentStatusRead]:
    try:
        overview = consent_service.list_consent_overview(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [
        ConsentStatusRead(
            code=definition.code,
            version_number=definition.version_number,
            title=definition.title,
            body_text=definition.body_text,
            is_required=definition.is_required,
            status=current.status if current else None,
            recorded_at=current.created_at if current else None,
        )
        for definition, current in overview
    ]


@router.post("/{code}/accept", response_model=UserConsentRead)
def accept_consent(
    filing_session_id: uuid.UUID,
    code: str,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> UserConsentRead:
    try:
        row = consent_service.accept_consent(db, filing_session_id, code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConsentDefinitionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return UserConsentRead(
        code=code, version_number=row.consent_definition.version_number, status=row.status, recorded_at=row.created_at
    )


@router.post("/{code}/withdraw", response_model=UserConsentRead)
def withdraw_consent(
    filing_session_id: uuid.UUID,
    code: str,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> UserConsentRead:
    try:
        row = consent_service.withdraw_consent(db, filing_session_id, code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConsentDefinitionNotFoundError, NoActiveConsentToWithdrawError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return UserConsentRead(
        code=code, version_number=row.consent_definition.version_number, status=row.status, recorded_at=row.created_at
    )
