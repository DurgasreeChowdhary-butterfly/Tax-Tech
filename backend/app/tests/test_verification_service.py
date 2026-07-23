import uuid
from decimal import Decimal

import pytest

from app.engines.extraction.errors import InvalidFieldValueError, UnsupportedFieldMappingError
from app.models.enums import VerificationAction
from app.models.salary_income import SalaryIncome
from app.repositories import verification as verification_repo
from app.services import verification as verification_service
from app.services.verification_errors import ExtractedFieldNotFoundError, MissingCorrectionValueError


def test_extraction_review_retrieval_lists_all_fields_with_support_flag(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document

    rows = verification_service.get_review_fields(db_session, filing_session.id, tax_document.id)

    by_name = {field.field_name: (verification, is_supported) for field, verification, is_supported in rows}
    assert by_name["employer_name"] == (None, True)
    assert by_name["gross_salary"] == (None, True)
    assert by_name["tds_deducted"] == (None, True)
    assert by_name["pan"] == (None, False)  # protected identity field: listed, but not actionable


def test_confirm_extracted_field_creates_verification_and_domain_record(db_session, extracted_document):
    filing_session, tax_document, extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    verification, domain_record = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
    )

    assert verification.action == VerificationAction.CONFIRM
    assert verification.verified_value == field.raw_value  # confirmed value == what was extracted
    assert isinstance(domain_record, SalaryIncome)
    assert domain_record.gross_salary == Decimal(field.raw_value)
    assert domain_record.document_extraction_id == extraction.id  # provenance


def test_correct_extracted_field_uses_user_supplied_value(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    verification, domain_record = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="1500000.00"
    )

    assert verification.action == VerificationAction.CORRECT
    assert verification.verified_value == "1500000.00"
    assert domain_record.gross_salary == Decimal("1500000.00")


def test_original_extracted_value_preserved_after_correction(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]
    original_raw_value = field.raw_value

    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="999999.00"
    )

    db_session.refresh(field)
    assert field.raw_value == original_raw_value  # untouched by the correction


def test_verified_domain_record_created_only_via_verification_workflow(db_session, extracted_document):
    filing_session, tax_document, _extraction, _fields_by_name = extracted_document

    # Extraction alone (already run by the fixture) must not have created any
    # domain record — only verify_field does that.
    assert db_session.query(SalaryIncome).count() == 0


def test_provenance_link_back_to_extraction(db_session, extracted_document):
    filing_session, tax_document, extraction, fields_by_name = extracted_document
    field = fields_by_name["employer_name"]

    _verification, domain_record = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
    )

    assert domain_record.document_extraction_id == extraction.id
    assert domain_record.tax_document_id == tax_document.id
    assert domain_record.filing_session_id == filing_session.id


def test_exact_retry_confirmation_is_idempotent(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    first, _ = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
    )
    second, _ = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
    )

    assert first.id == second.id
    history = verification_repo.get_verification_history(db_session, field.id)
    assert len(history) == 1


def test_exact_retry_correction_is_idempotent(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    first, _ = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="500000.00"
    )
    second, _ = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="500000.00"
    )

    assert first.id == second.id
    history = verification_repo.get_verification_history(db_session, field.id)
    assert len(history) == 1


def test_changed_correction_reconciles_domain_state_and_preserves_history(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    first, domain_after_first = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="500000.00"
    )
    second, domain_after_second = verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="600000.00"
    )

    assert first.id != second.id
    assert second.supersedes_id == first.id
    assert domain_after_second.gross_salary == Decimal("600000.00")  # reconciled to the new value

    history = verification_repo.get_verification_history(db_session, field.id)
    assert len(history) == 2
    assert history[0].is_current is False
    assert history[0].verified_value == "500000.00"  # old correction still visible in history
    assert history[1].is_current is True


def test_unsupported_field_mapping_rejected(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["pan"]

    with pytest.raises(UnsupportedFieldMappingError):
        verification_service.verify_field(
            db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
        )

    # No verification row and no domain record are created for a rejected field.
    assert verification_repo.get_current_verification(db_session, field.id) is None
    assert db_session.query(SalaryIncome).count() == 0


def test_invalid_financial_value_rejected(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    with pytest.raises(InvalidFieldValueError):
        verification_service.verify_field(
            db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value="-100.00"
        )

    assert verification_repo.get_current_verification(db_session, field.id) is None


def test_correct_without_value_is_rejected(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]

    with pytest.raises(MissingCorrectionValueError):
        verification_service.verify_field(
            db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT
        )


def test_cross_session_review_is_rejected(db_session, extracted_document):
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate
    from app.services.document_errors import DocumentNotFoundError

    _filing_session, tax_document, _extraction, fields_by_name = extracted_document
    other_user = create_user(db_session, UserCreate(email="other-verification@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))
    field = fields_by_name["gross_salary"]

    with pytest.raises(DocumentNotFoundError):
        verification_service.get_review_fields(db_session, other_session.id, tax_document.id)

    with pytest.raises(DocumentNotFoundError):
        verification_service.verify_field(
            db_session, other_session.id, tax_document.id, field.id, action=VerificationAction.CONFIRM
        )


def test_cross_document_field_confirmation_is_rejected(db_session, extracted_document, document_storage):
    """A field id from a DIFFERENT document (even in the same filing session's
    same user) must never be confirmable through another document's path."""
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate
    from app.services import document as document_service
    from app.services import extraction as extraction_service
    from app.repositories import document_processing as document_processing_repo

    filing_session, _tax_document, _extraction, fields_by_name = extracted_document

    other_user = create_user(db_session, UserCreate(email="other-document@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))
    other_document, _ = document_service.upload_document(
        db_session, other_session.id, original_filename="other.pdf",
        content=b"%PDF-1.4\n%different content\n", storage=document_storage,
    )
    other_job = extraction_service.start_extraction(db_session, other_session.id, other_document.id, storage=document_storage)
    other_extraction = document_processing_repo.get_extraction_for_job(db_session, other_job.id)
    other_fields = document_processing_repo.list_fields_for_extraction(db_session, other_extraction.id)
    other_field = next(f for f in other_fields if f.field_name == "gross_salary")

    field_from_original_doc = fields_by_name["gross_salary"]

    # Attempting to confirm the OTHER document's field via THIS filing_session/tax_document path must fail.
    with pytest.raises(ExtractedFieldNotFoundError):
        verification_service.verify_field(
            db_session, filing_session.id, _tax_document.id, other_field.id, action=VerificationAction.CONFIRM
        )

    assert field_from_original_doc.id != other_field.id


def test_unknown_field_id_is_rejected(db_session, extracted_document):
    filing_session, tax_document, _extraction, _fields_by_name = extracted_document

    with pytest.raises(ExtractedFieldNotFoundError):
        verification_service.verify_field(
            db_session, filing_session.id, tax_document.id, uuid.uuid4(), action=VerificationAction.CONFIRM
        )
