import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.integrations.ocr.base import FieldCandidate
from app.models.document_extraction import DocumentExtraction
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import ActorType, AuditEventCode, DocumentProcessingJobStatus, ExtractionFailureCode, ExtractionProviderName
from app.models.extracted_field import ExtractedField


def create_job(
    db: Session,
    tax_document_id: uuid.UUID,
    provider: ExtractionProviderName,
    *,
    filing_session_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> DocumentProcessingJob:
    """Starting a job is a direct user action (the user asked this document
    to be processed) — actor USER. The job's eventual COMPLETED/FAILED
    outcome (see mark_completed/mark_failed) is produced by the
    extraction worker, not a further user click — actor SYSTEM."""
    job = DocumentProcessingJob(tax_document_id=tax_document_id, provider=provider)
    db.add(job)
    db.flush()

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.EXTRACTION_STARTED,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type="document_processing_job",
        subject_id=job.id,
        metadata=None,
    )

    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, tax_document_id: uuid.UUID, job_id: uuid.UUID) -> DocumentProcessingJob | None:
    # Scoped by tax_document_id, not job_id alone — mirrors the Phase 5
    # ownership pattern so a job id can't be used to reach another document.
    stmt = select(DocumentProcessingJob).where(
        DocumentProcessingJob.id == job_id, DocumentProcessingJob.tax_document_id == tax_document_id
    )
    return db.execute(stmt).scalars().first()


def get_latest_job_for_document(db: Session, tax_document_id: uuid.UUID) -> DocumentProcessingJob | None:
    stmt = (
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.tax_document_id == tax_document_id)
        .order_by(DocumentProcessingJob.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def mark_running(db: Session, job: DocumentProcessingJob) -> DocumentProcessingJob:
    job.status = DocumentProcessingJobStatus.RUNNING
    db.commit()
    db.refresh(job)
    return job


def mark_failed(
    db: Session,
    job: DocumentProcessingJob,
    *,
    error_code: ExtractionFailureCode,
    error_detail: str,
    filing_session_id: uuid.UUID,
) -> DocumentProcessingJob:
    job.status = DocumentProcessingJobStatus.FAILED
    job.error_code = error_code
    # internal-only, bounded/sanitized (see sanitize_diagnostic_detail); never
    # serialize this via any API schema
    job.error_detail = error_detail

    # error_code only (a small fixed classification) — never error_detail,
    # which may embed exception class names not meant for the audit trail.
    audit_service.stage_event(
        db,
        event_code=AuditEventCode.EXTRACTION_FAILED,
        actor_type=ActorType.SYSTEM,
        filing_session_id=filing_session_id,
        subject_type="document_processing_job",
        subject_id=job.id,
        metadata={"error_code": error_code.value},
    )

    db.commit()
    db.refresh(job)
    return job


def mark_completed(db: Session, job: DocumentProcessingJob, *, filing_session_id: uuid.UUID) -> DocumentProcessingJob:
    job.status = DocumentProcessingJobStatus.COMPLETED

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.EXTRACTION_COMPLETED,
        actor_type=ActorType.SYSTEM,
        filing_session_id=filing_session_id,
        subject_type="document_processing_job",
        subject_id=job.id,
        metadata=None,
    )

    db.commit()
    db.refresh(job)
    return job


def create_extraction_with_fields(
    db: Session,
    *,
    document_processing_job_id: uuid.UUID,
    tax_document_id: uuid.UUID,
    provider: ExtractionProviderName,
    provider_version: str,
    raw_output: dict,
    fields: list[FieldCandidate],
) -> DocumentExtraction:
    extraction = DocumentExtraction(
        document_processing_job_id=document_processing_job_id,
        tax_document_id=tax_document_id,
        provider=provider,
        provider_version=provider_version,
        raw_output=raw_output,
    )
    db.add(extraction)
    db.flush()  # assign extraction.id before creating dependent field rows

    for field in fields:
        db.add(
            ExtractedField(
                document_extraction_id=extraction.id,
                field_name=field.field_name,
                raw_value=field.value,
                confidence=field.confidence,
            )
        )

    db.commit()
    db.refresh(extraction)
    return extraction


def get_extraction_for_job(db: Session, document_processing_job_id: uuid.UUID) -> DocumentExtraction | None:
    stmt = select(DocumentExtraction).where(DocumentExtraction.document_processing_job_id == document_processing_job_id)
    return db.execute(stmt).scalars().first()


def get_latest_extraction_for_document(db: Session, tax_document_id: uuid.UUID) -> DocumentExtraction | None:
    stmt = (
        select(DocumentExtraction)
        .where(DocumentExtraction.tax_document_id == tax_document_id)
        .order_by(DocumentExtraction.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def list_fields_for_extraction(db: Session, document_extraction_id: uuid.UUID) -> list[ExtractedField]:
    stmt = select(ExtractedField).where(ExtractedField.document_extraction_id == document_extraction_id)
    return list(db.execute(stmt).scalars().all())
