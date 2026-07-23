import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import ExtractionProviderName, VerificationAction
from app.models.extracted_field_verification import ExtractedFieldVerification
from app.models.interest_income import InterestIncome
from app.models.salary_income import SalaryIncome
from app.repositories import document_processing as document_processing_repo


def _extraction_for(db_session, tax_document):
    job = document_processing_repo.create_job(
        db_session,
        tax_document.id,
        ExtractionProviderName.MOCK,
        filing_session_id=tax_document.filing_session_id,
        actor_user_id=tax_document.filing_session.user_id,
    )
    from app.integrations.ocr.mock_provider import MockFormExtractionProvider

    return document_processing_repo.create_extraction_with_fields(
        db_session,
        document_processing_job_id=job.id,
        tax_document_id=tax_document.id,
        provider=ExtractionProviderName.MOCK,
        provider_version="test-v1",
        raw_output={},
        fields=MockFormExtractionProvider().extract(b"%PDF-1.4\n", "application/pdf").fields,
    )


def test_only_one_current_verification_per_field(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)
    field = document_processing_repo.list_fields_for_extraction(db_session, extraction.id)[0]

    db_session.add(
        ExtractedFieldVerification(extracted_field_id=field.id, action=VerificationAction.CONFIRM, verified_value="a")
    )
    db_session.commit()

    db_session.add(
        ExtractedFieldVerification(extracted_field_id=field.id, action=VerificationAction.CONFIRM, verified_value="b")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_salary_income_unique_per_extraction(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)

    db_session.add(SalaryIncome(filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id))
    db_session.commit()

    db_session.add(SalaryIncome(filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_salary_income_rejects_negative_amounts_at_db_level(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)

    row = SalaryIncome(
        filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id,
        gross_salary=-100,
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_interest_income_unique_per_extraction_and_non_negative(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)

    db_session.add(
        InterestIncome(filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id)
    )
    db_session.commit()

    db_session.add(
        InterestIncome(filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_extracted_field_cascades_to_verifications(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)
    field = document_processing_repo.list_fields_for_extraction(db_session, extraction.id)[0]

    db_session.add(
        ExtractedFieldVerification(extracted_field_id=field.id, action=VerificationAction.CONFIRM, verified_value="a")
    )
    db_session.commit()

    db_session.delete(field)
    db_session.commit()

    assert db_session.query(ExtractedFieldVerification).count() == 0


def test_deleting_extraction_cascades_to_domain_records(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    extraction = _extraction_for(db_session, tax_document)
    db_session.add(
        SalaryIncome(filing_session_id=_filing_session.id, tax_document_id=tax_document.id, document_extraction_id=extraction.id)
    )
    db_session.commit()

    db_session.delete(extraction)
    db_session.commit()

    assert db_session.query(SalaryIncome).count() == 0
