import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.enums import ActorType, AuditEventCode, DocumentStatus, StorageProviderName
from app.models.tax_document import TaxDocument


def create_document(
    db: Session,
    *,
    document_id: uuid.UUID,
    filing_session_id: uuid.UUID,
    original_filename: str,
    storage_key: str,
    storage_provider: StorageProviderName,
    content_type: str,
    size_bytes: int,
    content_hash: str,
    actor_user_id: uuid.UUID,
) -> TaxDocument:
    document = TaxDocument(
        id=document_id,
        filing_session_id=filing_session_id,
        original_filename=original_filename,
        storage_key=storage_key,
        storage_provider=storage_provider,
        content_type=content_type,
        size_bytes=size_bytes,
        content_hash=content_hash,
    )
    db.add(document)
    db.flush()

    # content_type only — never original_filename (user-chosen, may embed
    # personal info) or storage_key (never in audit metadata, per policy).
    audit_service.stage_event(
        db,
        event_code=AuditEventCode.DOCUMENT_UPLOADED,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type="tax_document",
        subject_id=document.id,
        metadata={"content_type": content_type},
    )

    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID) -> TaxDocument | None:
    # Always scoped by filing_session_id, never looked up by document_id alone
    # — this is what prevents cross-session/cross-user access via a guessed
    # or leaked document id.
    stmt = select(TaxDocument).where(
        TaxDocument.id == document_id, TaxDocument.filing_session_id == filing_session_id
    )
    return db.execute(stmt).scalars().first()


def get_active_document_by_hash(db: Session, filing_session_id: uuid.UUID, content_hash: str) -> TaxDocument | None:
    stmt = select(TaxDocument).where(
        TaxDocument.filing_session_id == filing_session_id,
        TaxDocument.content_hash == content_hash,
        TaxDocument.status == DocumentStatus.UPLOADED,
    )
    return db.execute(stmt).scalars().first()


def list_documents(db: Session, filing_session_id: uuid.UUID, *, include_deleted: bool = False) -> list[TaxDocument]:
    stmt = select(TaxDocument).where(TaxDocument.filing_session_id == filing_session_id)
    if not include_deleted:
        stmt = stmt.where(TaxDocument.status == DocumentStatus.UPLOADED)
    stmt = stmt.order_by(TaxDocument.created_at)
    return list(db.execute(stmt).scalars().all())


def mark_deleted(db: Session, document: TaxDocument, *, actor_user_id: uuid.UUID) -> TaxDocument:
    document.status = DocumentStatus.DELETED
    document.deleted_at = datetime.now(timezone.utc)

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.DOCUMENT_DELETED,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=document.filing_session_id,
        subject_type="tax_document",
        subject_id=document.id,
        metadata=None,
    )

    db.commit()
    db.refresh(document)
    return document
