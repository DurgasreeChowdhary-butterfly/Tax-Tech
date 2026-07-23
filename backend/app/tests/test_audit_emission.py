from app.models.enums import (
    ActorType,
    AuditEventCode,
    DocumentProcessingJobStatus,
    ExtractionFailureCode,
    FilerCategory,
    ResidencyStatus,
    TaxRegime,
    VerificationAction,
)
from app.repositories import audit_log as audit_log_repo
from app.repositories.filing_session import create_filing_session, update_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.user import UserCreate
from app.services import deduction as deduction_service
from app.services import document as document_service
from app.services import extraction as extraction_service
from app.services import questionnaire as questionnaire_service
from app.services import tax_calculation as tax_calculation_service
from app.services import verification as verification_service

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n"


def _codes(events):
    return [e.event_code for e in events]


def test_question_answer_created_and_changed_events(db_session, questionnaire_fixture):
    version, questions = questionnaire_fixture
    user = create_user(db_session, UserCreate(email="answer-audit@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    q1 = questions["has_other_income"]

    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, True)
    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, True)  # exact retry, idempotent
    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, False)  # genuine change

    events = [
        e
        for e in audit_log_repo.list_for_filing_session(db_session, filing_session.id)
        if e.event_code in (AuditEventCode.QUESTION_ANSWER_CREATED, AuditEventCode.QUESTION_ANSWER_CHANGED)
    ]
    assert _codes(events) == [AuditEventCode.QUESTION_ANSWER_CREATED, AuditEventCode.QUESTION_ANSWER_CHANGED]
    for event in events:
        assert event.actor_type == ActorType.USER
        assert event.actor_user_id == user.id
        assert event.event_metadata == {"question_code": "has_other_income"}


def test_flag_transitions_full_history_and_no_duplicate_on_repeat(db_session, decision_fixture):
    version, questions = decision_fixture
    user = create_user(db_session, UserCreate(email="flag-audit@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    q1 = questions["has_freelance_income"]

    # inactive -> active
    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, True)
    # repeated reconciliation with unchanged answers: no duplicate transition
    from app.services import decision as decision_service

    decision_service.reconcile_decision_state(db_session, filing_session.id)
    decision_service.reconcile_decision_state(db_session, filing_session.id)
    # active -> inactive
    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, False)
    # inactive -> active again (reactivation)
    questionnaire_service.submit_answer(db_session, filing_session.id, q1.id, True)

    flag_events = [
        e
        for e in audit_log_repo.list_for_filing_session(db_session, filing_session.id)
        if e.event_metadata and e.event_metadata.get("flag_code") == "FREELANCE_INCOME_DETECTED"
    ]
    assert _codes(flag_events) == [
        AuditEventCode.FILING_FLAG_ACTIVATED,
        AuditEventCode.FILING_FLAG_DEACTIVATED,
        AuditEventCode.FILING_FLAG_ACTIVATED,
    ]
    assert all(e.actor_type == ActorType.SYSTEM for e in flag_events)
    assert all(e.actor_user_id is None for e in flag_events)


def test_document_upload_and_delete_events(db_session, document_storage, consented_filing_session):
    filing_session = consented_filing_session

    document, _is_duplicate = document_service.upload_document(
        db_session, filing_session.id, original_filename="form16.pdf", content=PDF_BYTES, storage=document_storage
    )
    document_service.delete_document(db_session, filing_session.id, document.id, storage=document_storage)

    events = audit_log_repo.list_for_filing_session(db_session, filing_session.id)
    doc_events = [e for e in events if e.event_code in (AuditEventCode.DOCUMENT_UPLOADED, AuditEventCode.DOCUMENT_DELETED)]
    assert _codes(doc_events) == [AuditEventCode.DOCUMENT_UPLOADED, AuditEventCode.DOCUMENT_DELETED]
    assert all(e.actor_type == ActorType.USER and e.actor_user_id == filing_session.user_id for e in doc_events)
    assert doc_events[0].event_metadata == {"content_type": "application/pdf"}
    assert doc_events[0].subject_id == document.id
    assert doc_events[1].subject_id == document.id


def test_extraction_started_completed_events_and_actor_split(db_session, document_storage, consented_filing_session):
    filing_session = consented_filing_session
    document, _ = document_service.upload_document(
        db_session, filing_session.id, original_filename="form16.pdf", content=PDF_BYTES, storage=document_storage
    )

    extraction_service.start_extraction(db_session, filing_session.id, document.id, storage=document_storage)

    events = audit_log_repo.list_for_filing_session(db_session, filing_session.id)
    started = next(e for e in events if e.event_code == AuditEventCode.EXTRACTION_STARTED)
    completed = next(e for e in events if e.event_code == AuditEventCode.EXTRACTION_COMPLETED)

    # Starting extraction is a direct user action; the worker's outcome is system-generated.
    assert started.actor_type == ActorType.USER
    assert started.actor_user_id == filing_session.user_id
    assert completed.actor_type == ActorType.SYSTEM
    assert completed.actor_user_id is None
    assert started.subject_id == completed.subject_id  # same job


def test_extraction_failed_event_uses_safe_error_code_only(db_session, document_storage, consented_filing_session):
    from app.integrations.ocr.base import ExtractionFailedError

    filing_session = consented_filing_session
    document, _ = document_service.upload_document(
        db_session, filing_session.id, original_filename="form16.pdf", content=PDF_BYTES, storage=document_storage
    )

    class _FailingProvider:
        def extract(self, content, content_type):
            raise ExtractionFailedError("sensitive provider stack trace with a fake api-key=SECRET123")

    job = extraction_service.start_extraction(
        db_session, filing_session.id, document.id, provider=_FailingProvider(), storage=document_storage
    )
    assert job.status == DocumentProcessingJobStatus.FAILED

    events = audit_log_repo.list_for_filing_session(db_session, filing_session.id)
    failed = next(e for e in events if e.event_code == AuditEventCode.EXTRACTION_FAILED)
    assert failed.actor_type == ActorType.SYSTEM
    assert failed.event_metadata == {"error_code": ExtractionFailureCode.PROVIDER_ERROR.value}
    # the raw exception text must never leak into audit metadata
    serialized = str(failed.event_metadata)
    assert "SECRET123" not in serialized
    assert "stack trace" not in serialized


def test_extracted_field_confirm_and_correct_events(db_session, extracted_document):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    gross_field = fields_by_name["gross_salary"]
    tds_field = fields_by_name["tds_deducted"]

    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, gross_field.id, action=VerificationAction.CONFIRM
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, gross_field.id, action=VerificationAction.CONFIRM
    )  # exact repeat, idempotent — no duplicate event
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, tds_field.id, action=VerificationAction.CORRECT, value="12345.00"
    )

    events = audit_log_repo.list_for_filing_session(db_session, filing_session.id)
    verify_events = [
        e
        for e in events
        if e.event_code in (AuditEventCode.EXTRACTED_FIELD_CONFIRMED, AuditEventCode.EXTRACTED_FIELD_CORRECTED)
    ]
    assert _codes(verify_events) == [AuditEventCode.EXTRACTED_FIELD_CONFIRMED, AuditEventCode.EXTRACTED_FIELD_CORRECTED]
    assert verify_events[0].event_metadata == {"field_name": "gross_salary"}
    assert verify_events[1].event_metadata == {"field_name": "tds_deducted"}
    # the corrected value itself must never appear in audit metadata
    assert "12345" not in str(verify_events[1].event_metadata)


def test_deduction_claimed_and_changed_events(db_session):
    user = create_user(db_session, UserCreate(email="deduction-audit@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "50000.00")
    deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "50000.00")  # idempotent
    deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "75000.00")  # genuine change

    events = [
        e
        for e in audit_log_repo.list_for_filing_session(db_session, filing_session.id)
        if e.event_code in (AuditEventCode.DEDUCTION_CLAIMED, AuditEventCode.DEDUCTION_CHANGED)
    ]
    assert _codes(events) == [AuditEventCode.DEDUCTION_CLAIMED, AuditEventCode.DEDUCTION_CHANGED]
    assert all(e.event_metadata == {"code": "SECTION_80C"} for e in events)
    # claimed amounts must never appear in audit metadata
    assert all("50000" not in str(e.event_metadata) and "75000" not in str(e.event_metadata) for e in events)


def test_tax_calculation_created_and_recalculated_events(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["gross_salary"].id,
        action=VerificationAction.CORRECT, value="1000000.00",
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["tds_deducted"].id,
        action=VerificationAction.CORRECT, value="50000.00",
    )

    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)  # idempotent retry

    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["gross_salary"].id,
        action=VerificationAction.CORRECT, value="1200000.00",
    )
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)  # genuine recalculation

    events = [
        e
        for e in audit_log_repo.list_for_filing_session(db_session, filing_session.id)
        if e.event_code in (AuditEventCode.TAX_CALCULATION_CREATED, AuditEventCode.TAX_CALCULATION_RECALCULATED)
    ]
    assert _codes(events) == [AuditEventCode.TAX_CALCULATION_CREATED, AuditEventCode.TAX_CALCULATION_RECALCULATED]
    assert events[0].event_metadata["regime"] == "NEW"
    # no monetary figures anywhere in the audit metadata
    for event in events:
        assert "1000000" not in str(event.event_metadata)
        assert "1200000" not in str(event.event_metadata)


def test_consent_accepted_and_withdrawn_events_recorded(db_session, consent_definitions_v1):
    from app.services import consent as consent_service

    user = create_user(db_session, UserCreate(email="consent-event-audit@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    code = consent_definitions_v1[0].code

    consent_service.accept_consent(db_session, filing_session.id, code)
    consent_service.withdraw_consent(db_session, filing_session.id, code)

    events = [
        e
        for e in audit_log_repo.list_for_filing_session(db_session, filing_session.id)
        if e.event_code in (AuditEventCode.CONSENT_ACCEPTED, AuditEventCode.CONSENT_WITHDRAWN)
    ]
    assert _codes(events) == [AuditEventCode.CONSENT_ACCEPTED, AuditEventCode.CONSENT_WITHDRAWN]
    assert all(e.actor_type == ActorType.USER and e.actor_user_id == user.id for e in events)
    assert all(e.event_metadata["consent_code"] == code for e in events)


def test_no_forbidden_terms_anywhere_in_metadata_across_full_workflow(
    db_session, document_storage, consented_filing_session, real_fy2025_26_rule_set
):
    """End-to-end sanity sweep: build a realistic sequence of write paths and
    scan every resulting audit row's metadata for anything that looks like a
    financial value, PAN, or storage key."""
    filing_session = consented_filing_session
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )

    document, _ = document_service.upload_document(
        db_session, filing_session.id, original_filename="form16.pdf", content=PDF_BYTES, storage=document_storage
    )
    extraction_service.start_extraction(db_session, filing_session.id, document.id, storage=document_storage)
    extraction, fields = extraction_service.get_latest_extraction(db_session, filing_session.id, document.id)
    fields_by_name = {f.field_name: f for f in fields}
    verification_service.verify_field(
        db_session, filing_session.id, document.id, fields_by_name["gross_salary"].id,
        action=VerificationAction.CORRECT, value="987654.00",
    )
    verification_service.verify_field(
        db_session, filing_session.id, document.id, fields_by_name["tds_deducted"].id,
        action=VerificationAction.CORRECT, value="43210.00",
    )
    deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    events = audit_log_repo.list_for_filing_session(db_session, filing_session.id)
    assert len(events) > 5

    forbidden_fragments = ["987654", "43210", "150000", "form16.pdf", "filing-sessions/"]
    for event in events:
        blob = str(event.event_metadata or {})
        for fragment in forbidden_fragments:
            assert fragment not in blob, f"{event.event_code} metadata leaked {fragment!r}: {blob}"
