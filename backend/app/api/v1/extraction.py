import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.engines.extraction.errors import (
    DocumentProcessingJobNotFoundError,
    InvalidFieldValueError,
    NoExtractionAvailableError,
    UnsupportedFieldMappingError,
)
from app.integrations.ocr.base import ExtractionProvider
from app.integrations.ocr.provider import get_extraction_provider
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.provider import get_storage_provider
from app.models.filing_session import FilingSession
from app.models.salary_income import SalaryIncome
from app.schemas.extraction import DocumentExtractionRead, DocumentProcessingJobRead, ExtractedFieldRead
from app.schemas.verification import (
    ExtractedFieldVerificationRead,
    InterestIncomeRead,
    ReviewFieldRead,
    SalaryIncomeRead,
    VerifyFieldRequest,
    VerifyFieldResponse,
)
from app.services import extraction as extraction_service
from app.services import verification as verification_service
from app.services.document_errors import DocumentNotFoundError
from app.services.verification_errors import ExtractedFieldNotFoundError, MissingCorrectionValueError

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/documents/{document_id}/extraction", tags=["extraction"])


@router.post("", response_model=DocumentProcessingJobRead)
def start_extraction(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    provider: ExtractionProvider = Depends(get_extraction_provider),
    storage: StorageProvider = Depends(get_storage_provider),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentProcessingJobRead:
    try:
        job = extraction_service.start_extraction(
            db, filing_session_id, document_id, provider=provider, storage=storage
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentProcessingJobRead.model_validate(job)


@router.get("/jobs/{job_id}", response_model=DocumentProcessingJobRead)
def get_job(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentProcessingJobRead:
    try:
        job = extraction_service.get_job(db, filing_session_id, document_id, job_id)
    except (DocumentNotFoundError, DocumentProcessingJobNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentProcessingJobRead.model_validate(job)


@router.get("", response_model=DocumentExtractionRead)
def get_latest_extraction(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentExtractionRead:
    try:
        extraction, fields = extraction_service.get_latest_extraction(db, filing_session_id, document_id)
    except (DocumentNotFoundError, NoExtractionAvailableError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentExtractionRead(
        id=extraction.id,
        provider=extraction.provider,
        provider_version=extraction.provider_version,
        created_at=extraction.created_at,
        fields=[ExtractedFieldRead.model_validate(f) for f in fields],
    )


@router.get("/review", response_model=list[ReviewFieldRead])
def get_review_fields(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> list[ReviewFieldRead]:
    """Client-independent review listing: every extracted field, whether it
    can be confirmed/corrected at all (`is_supported`), and its current
    verification state, if any."""
    try:
        rows = verification_service.get_review_fields(db, filing_session_id, document_id)
    except (DocumentNotFoundError, NoExtractionAvailableError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [
        ReviewFieldRead(
            id=field.id,
            field_name=field.field_name,
            raw_value=field.raw_value,
            confidence=field.confidence,
            is_supported=is_supported,
            current_verification=(
                ExtractedFieldVerificationRead.model_validate(verification) if verification else None
            ),
        )
        for field, verification, is_supported in rows
    ]


@router.post("/fields/{field_id}/verify", response_model=VerifyFieldResponse)
def verify_field(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    body: VerifyFieldRequest,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> VerifyFieldResponse:
    try:
        verification, domain_record = verification_service.verify_field(
            db, filing_session_id, document_id, field_id, action=body.action, value=body.value
        )
    except (DocumentNotFoundError, ExtractedFieldNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (UnsupportedFieldMappingError, InvalidFieldValueError, MissingCorrectionValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = VerifyFieldResponse(verification=ExtractedFieldVerificationRead.model_validate(verification))
    if isinstance(domain_record, SalaryIncome):
        response.salary_income = SalaryIncomeRead.model_validate(domain_record)
    else:
        response.interest_income = InterestIncomeRead.model_validate(domain_record)
    return response
