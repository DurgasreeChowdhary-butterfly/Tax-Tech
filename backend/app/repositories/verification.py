import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.document_extraction import DocumentExtraction
from app.models.enums import ActorType, AuditEventCode, VerificationAction
from app.models.extracted_field import ExtractedField
from app.models.extracted_field_verification import ExtractedFieldVerification
from app.models.interest_income import InterestIncome
from app.models.salary_income import SalaryIncome


def get_field_in_document(db: Session, tax_document_id: uuid.UUID, field_id: uuid.UUID) -> ExtractedField | None:
    # Scoped through document_extractions.tax_document_id, not field_id alone
    # — prevents reaching a field belonging to a different document/session.
    stmt = (
        select(ExtractedField)
        .join(DocumentExtraction, ExtractedField.document_extraction_id == DocumentExtraction.id)
        .where(ExtractedField.id == field_id, DocumentExtraction.tax_document_id == tax_document_id)
    )
    return db.execute(stmt).scalars().first()


def get_current_verification(db: Session, extracted_field_id: uuid.UUID) -> ExtractedFieldVerification | None:
    stmt = select(ExtractedFieldVerification).where(
        ExtractedFieldVerification.extracted_field_id == extracted_field_id,
        ExtractedFieldVerification.is_current.is_(True),
    )
    return db.execute(stmt).scalars().first()


def get_verification_history(db: Session, extracted_field_id: uuid.UUID) -> list[ExtractedFieldVerification]:
    stmt = (
        select(ExtractedFieldVerification)
        .where(ExtractedFieldVerification.extracted_field_id == extracted_field_id)
        .order_by(ExtractedFieldVerification.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def record_verification(
    db: Session,
    *,
    extracted_field_id: uuid.UUID,
    action: VerificationAction,
    verified_value,
    actor_user_id: uuid.UUID,
    filing_session_id: uuid.UUID,
    field_name: str,
) -> ExtractedFieldVerification:
    """Idempotent: an exact repeat (same action + same value) of the current
    verification returns it unchanged — no new row. A genuine change (either
    action or value differs) creates a new row pointing back to what it
    supersedes and flips the old row non-current, mirroring question_answers.

    Stages EXTRACTED_FIELD_CONFIRMED/CORRECTED in the same transaction, on
    the genuine-change path only. `field_name` (e.g. "gross_salary") is the
    only value-adjacent audit metadata — the verified value itself is never
    included (data minimization: this is exactly the boundary where raw
    extraction becomes a verified financial figure).
    """
    current = get_current_verification(db, extracted_field_id)
    if current is not None and current.action == action and current.verified_value == verified_value:
        return current

    new_verification = ExtractedFieldVerification(
        extracted_field_id=extracted_field_id,
        action=action,
        verified_value=verified_value,
        is_current=True,
        supersedes_id=current.id if current else None,
    )
    if current is not None:
        current.is_current = False
    db.add(new_verification)
    db.flush()

    audit_service.stage_event(
        db,
        event_code=(
            AuditEventCode.EXTRACTED_FIELD_CONFIRMED
            if action == VerificationAction.CONFIRM
            else AuditEventCode.EXTRACTED_FIELD_CORRECTED
        ),
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type="extracted_field",
        subject_id=extracted_field_id,
        metadata={"field_name": field_name},
    )

    db.commit()
    db.refresh(new_verification)
    return new_verification


def get_or_create_salary_income(
    db: Session, *, filing_session_id: uuid.UUID, tax_document_id: uuid.UUID, document_extraction_id: uuid.UUID
) -> SalaryIncome:
    stmt = select(SalaryIncome).where(SalaryIncome.document_extraction_id == document_extraction_id)
    existing = db.execute(stmt).scalars().first()
    if existing is not None:
        return existing
    row = SalaryIncome(
        filing_session_id=filing_session_id, tax_document_id=tax_document_id, document_extraction_id=document_extraction_id
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_interest_income(
    db: Session, *, filing_session_id: uuid.UUID, tax_document_id: uuid.UUID, document_extraction_id: uuid.UUID
) -> InterestIncome:
    stmt = select(InterestIncome).where(InterestIncome.document_extraction_id == document_extraction_id)
    existing = db.execute(stmt).scalars().first()
    if existing is not None:
        return existing
    row = InterestIncome(
        filing_session_id=filing_session_id, tax_document_id=tax_document_id, document_extraction_id=document_extraction_id
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_salary_income_field(db: Session, row: SalaryIncome, column: str, value) -> SalaryIncome:
    setattr(row, column, value)
    db.commit()
    db.refresh(row)
    return row


def set_interest_income_field(db: Session, row: InterestIncome, column: str, value) -> InterestIncome:
    setattr(row, column, value)
    db.commit()
    db.refresh(row)
    return row


def get_salary_income_for_extraction(db: Session, document_extraction_id: uuid.UUID) -> SalaryIncome | None:
    stmt = select(SalaryIncome).where(SalaryIncome.document_extraction_id == document_extraction_id)
    return db.execute(stmt).scalars().first()


def get_interest_income_for_extraction(db: Session, document_extraction_id: uuid.UUID) -> InterestIncome | None:
    stmt = select(InterestIncome).where(InterestIncome.document_extraction_id == document_extraction_id)
    return db.execute(stmt).scalars().first()
