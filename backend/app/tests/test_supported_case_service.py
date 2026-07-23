import uuid

from app.models.enums import FilerCategory, ResidencyStatus, SupportedCaseOutcome
from app.repositories import filing_flag as filing_flag_repo
from app.repositories.filing_session import create_filing_session, update_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.user import UserCreate
from app.services import supported_case as supported_case_service

_OUTCOME_FLAG_CODES = {
    SupportedCaseOutcome.NOT_SUPPORTED: "SUPPORTED_CASE_NOT_SUPPORTED",
    SupportedCaseOutcome.REVIEW_REQUIRED: "SUPPORTED_CASE_REVIEW_REQUIRED",
    SupportedCaseOutcome.INCOMPLETE: "SUPPORTED_CASE_INCOMPLETE",
}


def _make_session(db_session, *, email, assessment_year="2026-27", **update_fields):
    user = create_user(db_session, UserCreate(email=email, password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year=assessment_year))
    if update_fields:
        session = update_filing_session(db_session, session, FilingSessionUpdate(**update_fields))
    return session


def _confirm_salary(db_session, filing_session, extracted_document, amount="1200000.00"):
    """Runs the real Phase 7 verification workflow so income only becomes
    'verified' the same way production data would."""
    from app.models.enums import VerificationAction
    from app.services import verification as verification_service

    _fs, tax_document, _extraction, fields_by_name = extracted_document
    field = fields_by_name["gross_salary"]
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, field.id, action=VerificationAction.CORRECT, value=amount
    )


def test_evaluate_persists_not_supported_flag_and_clears_others(db_session, published_tax_rule_set):
    session = _make_session(
        db_session,
        email="supported-case-1@example.com",
        residency_status=ResidencyStatus.RESIDENT,
        filer_category=FilerCategory.OTHER,
    )

    result = supported_case_service.evaluate_filing_session(db_session, session.id)

    assert result.outcome == SupportedCaseOutcome.NOT_SUPPORTED
    flags = {f.flag_code: f.is_active for f in filing_flag_repo.get_all_flags_for_session(db_session, session.id)}
    assert flags.get("SUPPORTED_CASE_NOT_SUPPORTED") is True
    assert flags.get("SUPPORTED_CASE_REVIEW_REQUIRED", False) is False
    assert flags.get("SUPPORTED_CASE_INCOMPLETE", False) is False


def test_idempotent_retry_makes_no_further_writes(db_session, published_tax_rule_set):
    session = _make_session(
        db_session,
        email="supported-case-2@example.com",
        residency_status=ResidencyStatus.RESIDENT,
        filer_category=FilerCategory.OTHER,
    )

    supported_case_service.evaluate_filing_session(db_session, session.id)
    flags_after_first = filing_flag_repo.get_all_flags_for_session(db_session, session.id)
    updated_at_first = {f.flag_code: f.updated_at for f in flags_after_first}

    supported_case_service.evaluate_filing_session(db_session, session.id)
    flags_after_second = filing_flag_repo.get_all_flags_for_session(db_session, session.id)
    updated_at_second = {f.flag_code: f.updated_at for f in flags_after_second}

    assert len(flags_after_first) == len(flags_after_second)
    assert updated_at_first == updated_at_second  # no row was touched on the unchanged retry


def test_changing_underlying_state_reconciles_outcome(db_session, published_tax_rule_set):
    session = _make_session(
        db_session,
        email="supported-case-3@example.com",
        residency_status=ResidencyStatus.RESIDENT,
        filer_category=FilerCategory.OTHER,
    )

    first = supported_case_service.evaluate_filing_session(db_session, session.id)
    assert first.outcome == SupportedCaseOutcome.NOT_SUPPORTED

    update_filing_session(db_session, session, FilingSessionUpdate(filer_category=FilerCategory.SALARIED))
    second = supported_case_service.evaluate_filing_session(db_session, session.id)
    # filer_category is now supported, but no verified income yet -> INCOMPLETE, not SUPPORTED.
    assert second.outcome == SupportedCaseOutcome.INCOMPLETE

    flags = {f.flag_code: f.is_active for f in filing_flag_repo.get_all_flags_for_session(db_session, session.id)}
    assert flags.get("SUPPORTED_CASE_NOT_SUPPORTED") is False
    assert flags.get("SUPPORTED_CASE_INCOMPLETE") is True


def test_unknown_filing_session_raises(db_session):
    try:
        supported_case_service.evaluate_filing_session(db_session, uuid.uuid4())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_cross_session_isolation(db_session, published_tax_rule_set):
    session_a = _make_session(
        db_session, email="isolation-a@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.OTHER,
    )
    session_b = _make_session(
        db_session, email="isolation-b@example.com",
        residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED,
    )

    result_a = supported_case_service.evaluate_filing_session(db_session, session_a.id)
    result_b = supported_case_service.evaluate_filing_session(db_session, session_b.id)

    assert result_a.outcome == SupportedCaseOutcome.NOT_SUPPORTED
    assert result_b.outcome == SupportedCaseOutcome.INCOMPLETE  # SALARIED but no verified income

    flags_a = {f.flag_code for f in filing_flag_repo.get_all_flags_for_session(db_session, session_a.id) if f.is_active}
    flags_b = {f.flag_code for f in filing_flag_repo.get_all_flags_for_session(db_session, session_b.id) if f.is_active}
    assert flags_a == {"SUPPORTED_CASE_NOT_SUPPORTED"}
    assert flags_b == {"SUPPORTED_CASE_INCOMPLETE"}


def test_supported_when_verified_salary_income_confirmed(db_session, published_tax_rule_set, extracted_document):
    filing_session, _tax_document, _extraction, _fields_by_name = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )

    before = supported_case_service.evaluate_filing_session(db_session, filing_session.id)
    assert before.outcome == SupportedCaseOutcome.INCOMPLETE
    assert "NO_VERIFIED_INCOME" in before.reasons

    _confirm_salary(db_session, filing_session, extracted_document)

    after = supported_case_service.evaluate_filing_session(db_session, filing_session.id)
    assert after.outcome == SupportedCaseOutcome.SUPPORTED
    assert after.reasons == ()


def test_unverified_extraction_alone_does_not_make_case_supported(db_session, published_tax_rule_set, extracted_document):
    """Instruction #9: unverified extraction data must never influence Phase 8
    outputs. The fixture's gross_salary field has been extracted but never
    confirmed/corrected — evaluate_filing_session must still see no verified
    income."""
    filing_session, _tax_document, _extraction, fields_by_name = extracted_document
    assert "gross_salary" in fields_by_name  # raw extraction exists...
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )

    result = supported_case_service.evaluate_filing_session(db_session, filing_session.id)

    assert result.outcome == SupportedCaseOutcome.INCOMPLETE
    assert "NO_VERIFIED_INCOME" in result.reasons
