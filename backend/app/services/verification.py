import uuid

from sqlalchemy.orm import Session

from app.engines.extraction.errors import NoExtractionAvailableError
from app.engines.extraction.field_mapping import resolve_mapping, validate_mapped_value
from app.models.enums import VerificationAction
from app.models.extracted_field import ExtractedField
from app.models.extracted_field_verification import ExtractedFieldVerification
from app.models.tax_document import TaxDocument
from app.repositories import document_processing as document_processing_repo
from app.repositories import verification as verification_repo
from app.services import document as document_service
from app.services.questionnaire import get_filing_session_or_raise
from app.services.verification_errors import ExtractedFieldNotFoundError, MissingCorrectionValueError


def _get_scoped_field(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID, field_id: uuid.UUID
) -> tuple[TaxDocument, ExtractedField]:
    # Ownership chain, each link checked: session -> document (reuses Phase 5's
    # scoped lookup) -> extraction -> field (joined, not looked up by field id
    # alone). A field id from another document/session can never resolve here.
    tax_document = document_service.get_document(db, filing_session_id, document_id)
    field = verification_repo.get_field_in_document(db, tax_document.id, field_id)
    if field is None:
        raise ExtractedFieldNotFoundError(field_id)
    return tax_document, field


def verify_field(
    db: Session,
    filing_session_id: uuid.UUID,
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    *,
    action: VerificationAction,
    value=None,
) -> tuple[ExtractedFieldVerification, object]:
    """CONFIRM copies the field's raw_value unchanged; CORRECT requires an
    explicit replacement value. Both are validated against the field's static
    domain mapping BEFORE anything is written: an unsupported field name
    (e.g. `pan` — see field_mapping.py) or an invalid value creates no
    verification row and no domain record at all.

    Idempotent: an exact repeat of the current verification (same action,
    same value) is a no-op — no new row. A genuine change always overwrites
    the mapped domain column to match, so the domain state never goes stale.
    """
    tax_document, field = _get_scoped_field(db, filing_session_id, document_id, field_id)

    if action == VerificationAction.CONFIRM:
        candidate_value = field.raw_value
    elif action == VerificationAction.CORRECT:
        if value is None:
            raise MissingCorrectionValueError()
        candidate_value = value
    else:
        raise ValueError(f"unsupported verification action {action!r}")

    mapping, validated_value = validate_mapped_value(field.field_name, candidate_value)

    filing_session = get_filing_session_or_raise(db, filing_session_id)
    verification = verification_repo.record_verification(
        db,
        extracted_field_id=field.id,
        action=action,
        verified_value=candidate_value,
        actor_user_id=filing_session.user_id,
        filing_session_id=filing_session_id,
        field_name=field.field_name,
    )

    domain_record = _upsert_domain_value(
        db,
        mapping,
        filing_session_id=filing_session_id,
        tax_document_id=tax_document.id,
        document_extraction_id=field.document_extraction_id,
        value=validated_value,
    )

    return verification, domain_record


def _upsert_domain_value(db: Session, mapping, *, filing_session_id, tax_document_id, document_extraction_id, value):
    if mapping.domain_table == "salary_income":
        row = verification_repo.get_or_create_salary_income(
            db,
            filing_session_id=filing_session_id,
            tax_document_id=tax_document_id,
            document_extraction_id=document_extraction_id,
        )
        return verification_repo.set_salary_income_field(db, row, mapping.column, value)
    if mapping.domain_table == "interest_income":
        row = verification_repo.get_or_create_interest_income(
            db,
            filing_session_id=filing_session_id,
            tax_document_id=tax_document_id,
            document_extraction_id=document_extraction_id,
        )
        return verification_repo.set_interest_income_field(db, row, mapping.column, value)
    raise ValueError(f"unknown domain table {mapping.domain_table!r}")  # pragma: no cover - unreachable, closed set


def get_review_fields(
    db: Session, filing_session_id: uuid.UUID, document_id: uuid.UUID
) -> list[tuple[ExtractedField, ExtractedFieldVerification | None, bool]]:
    """For the review screen: every field on the document's latest extraction,
    its current verification (if any), and whether it even has a supported
    domain mapping (client-independent — the client doesn't need to know the
    mapping rules, just whether a given field is actionable)."""
    tax_document = document_service.get_document(db, filing_session_id, document_id)
    extraction = document_processing_repo.get_latest_extraction_for_document(db, tax_document.id)
    if extraction is None:
        raise NoExtractionAvailableError(tax_document.id)
    fields = document_processing_repo.list_fields_for_extraction(db, extraction.id)

    results = []
    for field in fields:
        verification = verification_repo.get_current_verification(db, field.id)
        is_supported = resolve_mapping(field.field_name) is not None
        results.append((field, verification, is_supported))
    return results
