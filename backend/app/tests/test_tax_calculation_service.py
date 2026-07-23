import uuid
from decimal import Decimal

import pytest

from app.engines.tax.errors import CaseNotSupportedForCalculationError
from app.models.enums import FilerCategory, ResidencyStatus, TaxRegime, VerificationAction
from app.repositories import tax_calculation as tax_calculation_repo
from app.repositories.filing_session import update_filing_session
from app.repositories.user import create_user
from app.repositories.filing_session import create_filing_session
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.user import UserCreate
from app.services import deduction as deduction_service
from app.services import tax_calculation as tax_calculation_service
from app.services import verification as verification_service


def _confirm_salary(db_session, extracted_document, *, gross_salary="1000000.00", tds="50000.00"):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    gross_field = fields_by_name["gross_salary"]
    tds_field = fields_by_name["tds_deducted"]
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, gross_field.id,
        action=VerificationAction.CORRECT, value=gross_salary,
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, tds_field.id,
        action=VerificationAction.CORRECT, value=tds,
    )
    return filing_session


def _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set, **overrides):
    filing_session, *_ = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    gross_salary = overrides.pop("gross_salary", "1000000.00")
    tds = overrides.pop("tds", "50000.00")
    return _confirm_salary(db_session, extracted_document, gross_salary=gross_salary, tds=tds)


def test_supported_case_required_for_calculation(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session, *_ = extracted_document  # residency/filer_category left unset -> INCOMPLETE
    with pytest.raises(CaseNotSupportedForCalculationError) as exc_info:
        tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    assert exc_info.value.outcome == "INCOMPLETE"


def test_not_supported_case_blocked(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session, *_ = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.NON_RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    with pytest.raises(CaseNotSupportedForCalculationError) as exc_info:
        tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    assert exc_info.value.outcome == "NOT_SUPPORTED"


def test_no_published_rule_set_blocks_calculation_via_supported_case_gate(db_session, extracted_document):
    """No tax_rule_set at all is published for this session's assessment year
    -> the Supported Case Validator already returns NOT_SUPPORTED for this
    exact reason (NO_PUBLISHED_RULE_SET), so calculation is blocked before
    ever reaching calculate_tax's own (defense-in-depth) rule-set check.
    Covers both 'no published rule set blocked' and (below) 'draft rule set
    rejected' — a draft-only rule set is indistinguishable from none at all
    from get_published_rule_set_for_assessment_year's point of view."""
    filing_session, *_ = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    _confirm_salary(db_session, extracted_document)

    with pytest.raises(CaseNotSupportedForCalculationError) as exc_info:
        tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    assert exc_info.value.outcome == "NOT_SUPPORTED"
    assert tax_calculation_repo.get_current_calculation(db_session, filing_session.id, TaxRegime.NEW) is None


def test_draft_rule_set_is_never_used_for_calculation(db_session, extracted_document):
    from app.repositories import tax_rule_set as tax_rule_set_repo

    filing_session, *_ = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    _confirm_salary(db_session, extracted_document)

    draft_rule_set = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2026-27", engine_version="v-draft")
    from app.models.enums import TaxRuleType

    tax_rule_set_repo.add_tax_rule(
        db_session, draft_rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.SLAB, code="SLAB_1",
        parameters={"min": "0.00", "max": None, "rate": "0.00"},
    )
    # Deliberately never published.

    with pytest.raises(CaseNotSupportedForCalculationError):
        tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)


def test_verified_domain_only_boundary_unconfirmed_extraction_ignored(db_session, extracted_document, real_fy2025_26_rule_set):
    """A field being extracted (raw) but never confirmed must never influence
    the calculation — the Supported Case Validator already blocks this as
    INCOMPLETE (no verified income), which is itself the enforcement of the
    extraction-to-tax trust boundary at the calculation entry point."""
    filing_session, *_ = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    with pytest.raises(CaseNotSupportedForCalculationError) as exc_info:
        tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    assert exc_info.value.outcome == "INCOMPLETE"
    assert tax_calculation_repo.get_current_calculation(db_session, filing_session.id, TaxRegime.NEW) is None


def test_exact_retry_is_idempotent(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)

    first, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    second, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    assert first.id == second.id
    history = tax_calculation_repo.get_calculation_history(db_session, filing_session.id, TaxRegime.NEW)
    assert len(history) == 1


def test_changed_verified_input_creates_next_calculation_version(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)
    first, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    _confirm_salary(db_session, extracted_document, gross_salary="1300000.00", tds="50000.00")
    second, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    assert second.id != first.id
    assert second.gross_total_income != first.gross_total_income
    history = tax_calculation_repo.get_calculation_history(db_session, filing_session.id, TaxRegime.NEW)
    assert len(history) == 2
    assert history[0].id == first.id
    assert history[1].id == second.id
    db_session.refresh(first)
    assert first.is_current is False
    assert second.is_current is True
    assert second.supersedes_id == first.id
    # Immutable historical calculation: the old row's own figures were never rewritten.
    assert first.gross_total_income == Decimal("925000.00")


def test_changed_rule_set_version_creates_next_calculation_version(db_session, extracted_document, real_fy2025_26_rule_set):
    from app.engines.tax.rule_data import FY_2025_26_RULES
    from app.repositories import tax_rule_set as tax_rule_set_repo

    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)
    first, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    v2 = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2026-27", engine_version="v2")
    for rule in FY_2025_26_RULES:
        tax_rule_set_repo.add_tax_rule(
            db_session, v2, regime=rule["regime"], rule_type=rule["rule_type"], code=rule["code"],
            order_index=rule["order_index"], parameters=rule["parameters"],
        )
    tax_rule_set_repo.publish_tax_rule_set(db_session, v2)

    second, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    assert second.id != first.id
    assert second.tax_rule_set_id == v2.id
    assert first.tax_rule_set_id == real_fy2025_26_rule_set.id
    # Same verified inputs, same numeric rules -> same figures, but still a genuinely new version.
    assert second.gross_total_income == first.gross_total_income


def test_old_and_new_regime_calculations_are_independent(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)

    new_calc, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    old_calc, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.OLD)

    assert new_calc.id != old_calc.id
    assert new_calc.regime == TaxRegime.NEW
    assert old_calc.regime == TaxRegime.OLD
    assert new_calc.total_tax_liability != old_calc.total_tax_liability
    # Recalculating NEW must not disturb the OLD regime's current row.
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)
    still_old = tax_calculation_repo.get_current_calculation(db_session, filing_session.id, TaxRegime.OLD)
    assert still_old.id == old_calc.id


def test_cross_session_isolation(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    other_user = create_user(db_session, UserCreate(email="calc-cross-session@example.com", password="TestPassword123!"))
    other_session = create_filing_session(db_session, FilingSessionCreate(user_id=other_user.id, assessment_year="2026-27"))

    with pytest.raises(CaseNotSupportedForCalculationError):  # no income at all for this session -> INCOMPLETE
        tax_calculation_service.calculate_tax(db_session, other_session.id, TaxRegime.NEW)

    assert tax_calculation_repo.get_current_calculation(db_session, other_session.id, TaxRegime.NEW) is None
    assert tax_calculation_repo.get_current_calculation(db_session, filing_session.id, TaxRegime.NEW) is not None


def test_unknown_filing_session_raises(db_session, real_fy2025_26_rule_set):
    with pytest.raises(ValueError):
        tax_calculation_service.calculate_tax(db_session, uuid.uuid4(), TaxRegime.NEW)


def test_deduction_claim_affects_calculation_only_after_being_recomputed(db_session, extracted_document, real_fy2025_26_rule_set):
    filing_session = _make_supported_session(db_session, extracted_document, real_fy2025_26_rule_set)
    before, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.OLD)

    deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    after, _ = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.OLD)

    assert after.id != before.id
    assert after.total_deductions_applied == Decimal("150000.00")
    assert after.taxable_income < before.taxable_income
