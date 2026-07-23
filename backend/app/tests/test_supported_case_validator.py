"""Table-driven tests for the Supported Case Validator, per docs/PRODUCT_SCOPE.md's
supported/excluded list and docs/IMPLEMENTATION_PLAN.md Phase 8 exit criteria.
Pure function tests — no DB required.
"""

import pytest

from app.engines.tax.supported_case import SupportedCaseInput, evaluate_supported_case
from app.models.enums import FilerCategory, FilingComplexity, ResidencyStatus, SupportedCaseOutcome

_BASE = dict(
    filer_category=FilerCategory.SALARIED,
    residency_status=ResidencyStatus.RESIDENT,
    session_complexity=FilingComplexity.SIMPLE,
    active_flag_codes=frozenset(),
    has_published_rule_set=True,
    has_verified_income=True,
)


def _inputs(**overrides):
    return SupportedCaseInput(**{**_BASE, **overrides})


@pytest.mark.parametrize(
    "name, overrides, expected_outcome",
    [
        ("salaried_single_employer_supported", {}, SupportedCaseOutcome.SUPPORTED),
        (
            "freelance_income_present",
            {"active_flag_codes": frozenset({"FREELANCE_INCOME_DETECTED"})},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "business_income_present",
            {"active_flag_codes": frozenset({"BUSINESS_INCOME_DETECTED"})},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "capital_gains_unsupported",
            {"active_flag_codes": frozenset({"CAPITAL_GAINS_UNSUPPORTED_DETECTED"})},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "crypto_income_present",
            {"active_flag_codes": frozenset({"CRYPTO_INCOME_DETECTED"})},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "foreign_income_present",
            {"active_flag_codes": frozenset({"FOREIGN_INCOME_DETECTED"})},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "residency_not_ordinarily_resident",
            {"residency_status": ResidencyStatus.RESIDENT_NOT_ORDINARILY_RESIDENT},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        (
            "residency_non_resident",
            {"residency_status": ResidencyStatus.NON_RESIDENT},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        ("filer_category_other", {"filer_category": FilerCategory.OTHER}, SupportedCaseOutcome.NOT_SUPPORTED),
        (
            "decision_engine_complexity_not_supported",
            {"session_complexity": FilingComplexity.NOT_SUPPORTED},
            SupportedCaseOutcome.NOT_SUPPORTED,
        ),
        ("no_published_rule_set", {"has_published_rule_set": False}, SupportedCaseOutcome.NOT_SUPPORTED),
        (
            "complexity_review_required",
            {"session_complexity": FilingComplexity.REVIEW_REQUIRED},
            SupportedCaseOutcome.REVIEW_REQUIRED,
        ),
        (
            "review_required_flag_active",
            {"active_flag_codes": frozenset({"REVIEW_REQUIRED"})},
            SupportedCaseOutcome.REVIEW_REQUIRED,
        ),
        ("filer_category_missing", {"filer_category": None}, SupportedCaseOutcome.INCOMPLETE),
        ("residency_status_missing", {"residency_status": None}, SupportedCaseOutcome.INCOMPLETE),
        ("no_verified_income_yet", {"has_verified_income": False}, SupportedCaseOutcome.INCOMPLETE),
    ],
)
def test_supported_case_fixture_scenarios(name, overrides, expected_outcome):
    result = evaluate_supported_case(_inputs(**overrides))
    assert result.outcome == expected_outcome, name


def test_not_supported_takes_precedence_over_review_required():
    result = evaluate_supported_case(
        _inputs(
            active_flag_codes=frozenset({"FREELANCE_INCOME_DETECTED", "REVIEW_REQUIRED"}),
            session_complexity=FilingComplexity.REVIEW_REQUIRED,
        )
    )
    assert result.outcome == SupportedCaseOutcome.NOT_SUPPORTED


def test_not_supported_takes_precedence_over_incomplete():
    result = evaluate_supported_case(
        _inputs(filer_category=FilerCategory.OTHER, residency_status=None, has_verified_income=False)
    )
    assert result.outcome == SupportedCaseOutcome.NOT_SUPPORTED


def test_review_required_takes_precedence_over_incomplete():
    result = evaluate_supported_case(
        _inputs(
            session_complexity=FilingComplexity.REVIEW_REQUIRED,
            filer_category=None,
            has_verified_income=False,
        )
    )
    assert result.outcome == SupportedCaseOutcome.REVIEW_REQUIRED


def test_supported_case_has_no_reasons():
    result = evaluate_supported_case(_inputs())
    assert result.outcome == SupportedCaseOutcome.SUPPORTED
    assert result.reasons == ()


def test_reasons_are_fixed_safe_codes_not_free_text():
    result = evaluate_supported_case(
        _inputs(filer_category=FilerCategory.OTHER, active_flag_codes=frozenset({"FREELANCE_INCOME_DETECTED"}))
    )
    assert result.outcome == SupportedCaseOutcome.NOT_SUPPORTED
    assert "FILER_CATEGORY_UNSUPPORTED" in result.reasons
    assert "UNSUPPORTED_SCENARIO:FREELANCE_INCOME_DETECTED" in result.reasons
