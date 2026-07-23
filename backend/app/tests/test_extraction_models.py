import pytest
from sqlalchemy.exc import IntegrityError

from app.models.document_extraction import DocumentExtraction
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import ExtractionProviderName
from app.models.extracted_field import ExtractedField


def test_only_one_extraction_per_job(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    job = DocumentProcessingJob(tax_document_id=tax_document.id, provider=ExtractionProviderName.MOCK)
    db_session.add(job)
    db_session.commit()

    db_session.add(
        DocumentExtraction(
            document_processing_job_id=job.id,
            tax_document_id=tax_document.id,
            provider=ExtractionProviderName.MOCK,
            provider_version="v1",
            raw_output={"fields": []},
        )
    )
    db_session.commit()

    db_session.add(
        DocumentExtraction(
            document_processing_job_id=job.id,
            tax_document_id=tax_document.id,
            provider=ExtractionProviderName.MOCK,
            provider_version="v1",
            raw_output={"fields": []},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_confidence_must_be_within_zero_and_one(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    job = DocumentProcessingJob(tax_document_id=tax_document.id, provider=ExtractionProviderName.MOCK)
    db_session.add(job)
    db_session.commit()

    extraction = DocumentExtraction(
        document_processing_job_id=job.id,
        tax_document_id=tax_document.id,
        provider=ExtractionProviderName.MOCK,
        provider_version="v1",
        raw_output={},
    )
    db_session.add(extraction)
    db_session.commit()

    db_session.add(
        ExtractedField(document_extraction_id=extraction.id, field_name="x", raw_value="y", confidence=1.5)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_job_cascades_to_extraction_and_fields(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    job = DocumentProcessingJob(tax_document_id=tax_document.id, provider=ExtractionProviderName.MOCK)
    db_session.add(job)
    db_session.commit()

    extraction = DocumentExtraction(
        document_processing_job_id=job.id,
        tax_document_id=tax_document.id,
        provider=ExtractionProviderName.MOCK,
        provider_version="v1",
        raw_output={},
    )
    db_session.add(extraction)
    db_session.commit()
    db_session.add(ExtractedField(document_extraction_id=extraction.id, field_name="x", raw_value="y", confidence=0.5))
    db_session.commit()

    db_session.delete(job)
    db_session.commit()

    assert db_session.query(DocumentExtraction).count() == 0
    assert db_session.query(ExtractedField).count() == 0


def test_deleting_tax_document_cascades_to_jobs(db_session, uploaded_document):
    _filing_session, tax_document = uploaded_document
    db_session.add(DocumentProcessingJob(tax_document_id=tax_document.id, provider=ExtractionProviderName.MOCK))
    db_session.commit()

    db_session.delete(tax_document)
    db_session.commit()

    assert db_session.query(DocumentProcessingJob).count() == 0
