import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_owned_filing_session
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.provider import get_storage_provider
from app.models.filing_session import FilingSession
from app.schemas.document import DocumentListResponse, DocumentRead, DocumentUploadResponse
from app.services import document as document_service
from app.services.consent_errors import MissingRequiredConsentError
from app.services.document_errors import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    StorageObjectMissingError,
    UnsupportedFileTypeError,
)

router = APIRouter(prefix="/filing-sessions/{filing_session_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    filing_session_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentUploadResponse:
    content = await file.read()
    try:
        document, is_duplicate = document_service.upload_document(
            db, filing_session_id, original_filename=file.filename or "", content=content, storage=storage
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingRequiredConsentError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (EmptyFileError, FileTooLargeError, UnsupportedFileTypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DocumentUploadResponse(document=DocumentRead.model_validate(document), is_duplicate=is_duplicate)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    filing_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentListResponse:
    try:
        documents = document_service.list_documents(db, filing_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentListResponse(documents=[DocumentRead.model_validate(d) for d in documents])


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentRead:
    try:
        document = document_service.get_document(db, filing_session_id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentRead.model_validate(document)


@router.get("/{document_id}/content")
def get_document_content(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> Response:
    # Backend-mediated retrieval only — bytes are read from private storage
    # and returned directly in the response body. No public or signed URL is
    # ever generated or stored.
    try:
        content, content_type, _filename = document_service.get_document_content(
            db, filing_session_id, document_id, storage=storage
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StorageObjectMissingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(content=content, media_type=content_type)


@router.delete("/{document_id}", response_model=DocumentRead)
def delete_document(
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
    _owned_filing_session: FilingSession = Depends(get_owned_filing_session),
) -> DocumentRead:
    try:
        document = document_service.delete_document(db, filing_session_id, document_id, storage=storage)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentRead.model_validate(document)
