"""Golden-fixture tests for the pure calculation engine (app/engines/tax/calculation.py).

Every expected value below is HAND-DERIVED from the officially-sourced rule
data in app/engines/tax/rule_data.py (see that module's docstring for exact
citations) — never copied from running the engine. Each test comment shows
the arithmetic derivation so the expectation can be independently checked
against the rules.
"""

from decimal import Decimal

import pytest

from app.engines.tax.calculation import calculate
from app.engines.tax.errors import SurchargeNotSupportedError
from app.engines.tax.rule_data import FY_2025_26_RULES
from app.models.enums import TaxRegime
from app.models.tax_rule import TaxRule


def _rules_for(regime: TaxRegime) -> list[TaxRule]:
    return [
        TaxRule(regime=r["regime"], rule_type=r["rule_type"], code=r["code"], order_index=r["order_index"], parameters=r["parameters"])
        for r in FY_2025_26_RULES
        if r["regime"] == regime
    ]


@pytest.fixture()
def new_rules():
    return _rules_for(TaxRegime.NEW)


@pytest.fixture()
def old_rules():
    return _rules_for(TaxRegime.OLD)


def _calc(rules, *, gross_salary="0.00", tds="0.00", interest="0.00", deductions=None):
    return calculate(
        rules=rules,
        total_gross_salary=Decimal(gross_salary),
        total_tds_deducted=Decimal(tds),
        total_interest_income=Decimal(interest),
        deduction_claims=deductions or {},
    )


# --- Golden Case 1: new regime, salary only, single employer ---
# gross=1,000,000; std_ded(new)=75,000 -> income_from_salary=925,000; GTI=925,000
# taxable=925,000 (already x10)
# slabs: 0-4L:0; 4-8L@5%=20,000; 8-9.25L@10%=12,500 => tax_before_rebate=32,500
# taxable<=12,00,000 threshold -> rebate=min(32500,60000)=32,500 -> tax_after=0; cess=0; total=0
# net_payable = 0 - 50,000(tds) = -50,000 (refund)
def test_golden_new_regime_salary_only_single_employer(new_rules):
    result = _calc(new_rules, gross_salary="1000000.00", tds="50000.00")
    assert result.gross_total_income == Decimal("925000.00")
    assert result.taxable_income == Decimal("925000")
    assert result.tax_before_rebate == Decimal("32500.00")
    assert result.rebate_amount == Decimal("32500.00")
    assert result.tax_after_rebate == Decimal("0.00")
    assert result.cess_amount == Decimal("0.00")
    assert result.total_tax_liability == Decimal("0")
    assert result.net_payable == Decimal("-50000.00")


# --- Golden Case 2: old regime, same salary, Section 80C claimed in full ---
# gross=1,000,000; std_ded(old)=50,000 -> income_from_salary=950,000; GTI=950,000
# 80C: claimed=150,000, cap=150,000 -> eligible=applied=150,000
# taxable_before_rounding=950,000-150,000=800,000 (already x10)
# slabs: 0-2.5L:0; 2.5-5L@5%=12,500; 5-8L@20%=60,000 => tax_before_rebate=72,500
# taxable(800,000)>5,00,000 threshold, old regime has NO marginal relief -> rebate=0
# tax_after_rebate=72,500; cess=72,500*0.04=2,900.00 => 75,400.00 -> round(75400)=75400
# net_payable = 75,400 - 50,000(tds) = 25,400 (payable)
def test_golden_old_regime_salary_with_full_section_80c(old_rules):
    result = _calc(old_rules, gross_salary="1000000.00", tds="50000.00", deductions={"SECTION_80C": Decimal("150000.00")})
    assert result.gross_total_income == Decimal("950000.00")
    assert result.total_deductions_applied == Decimal("150000.00")
    assert result.taxable_income == Decimal("800000")
    assert result.tax_before_rebate == Decimal("72500.00")
    assert result.rebate_amount == Decimal("0.00")
    assert result.tax_after_rebate == Decimal("72500.00")
    assert result.cess_amount == Decimal("2900.00")
    assert result.total_tax_liability == Decimal("75400")
    assert result.net_payable == Decimal("25400.00")


# --- Golden Case 3: multi-employer, new regime, exercising marginal relief ---
# gross = 600,000 + 700,000 = 1,300,000; tds = 20,000+25,000=45,000
# std_ded=75,000 -> income_from_salary=1,225,000; GTI=1,225,000 (already x10)
# slabs: 0-4L:0;4-8L@5%=20,000;8-12L@10%=40,000;12-12.25L@15%=3,750 => tax_before_rebate=63,750
# excess over 12,00,000 threshold = 25,000; marginal relief (new regime):
#   tax_before_rebate(63,750) > excess(25,000) -> rebate = 63,750-25,000 = 38,750
# tax_after_rebate = 25,000; cess = 25,000*0.04=1,000 => total=26,000 -> round(26000)=26000
# net_payable = 26,000 - 45,000 = -19,000 (refund)
def test_golden_new_regime_multi_employer_with_marginal_relief(new_rules):
    result = _calc(new_rules, gross_salary="1300000.00", tds="45000.00")
    assert result.gross_total_income == Decimal("1225000.00")
    assert result.taxable_income == Decimal("1225000")
    assert result.tax_before_rebate == Decimal("63750.00")
    assert result.rebate_amount == Decimal("38750.00")
    assert result.tax_after_rebate == Decimal("25000.00")
    assert result.cess_amount == Decimal("1000.00")
    assert result.total_tax_liability == Decimal("26000")
    assert result.net_payable == Decimal("-19000.00")


# --- Golden Case 4: new regime, exact Section 87A rebate boundary ---
# taxable_income target = 12,00,000 exactly -> gross_salary = 12,00,000+75,000=12,75,000
# slabs: 0-4L:0;4-8L@5%=20,000;8-12L@10%=40,000 => tax_before_rebate=60,000
# taxable<=threshold -> rebate=min(60000,60000)=60,000 -> tax_after=0; cess=0; total=0
def test_golden_new_regime_exact_rebate_boundary(new_rules):
    result = _calc(new_rules, gross_salary="1275000.00")
    assert result.taxable_income == Decimal("1200000")
    assert result.tax_before_rebate == Decimal("60000.00")
    assert result.rebate_amount == Decimal("60000.00")
    assert result.total_tax_liability == Decimal("0")


# --- Golden Case 5: new regime, immediately ABOVE the rebate boundary (+10) ---
# taxable_income target = 12,00,010 -> gross_salary = 12,00,010+75,000=12,75,010
# slabs: 0-4L:0;4-8L@5%=20,000;8-12L@10%=40,000;12L-1,200,010@15%=10*0.15=1.50
#   => tax_before_rebate = 60,001.50
# excess = 10; marginal relief: tax_before_rebate(60,001.50) > excess(10)
#   -> rebate = 60,001.50 - 10 = 59,991.50 -> tax_after_rebate = 10.00
# cess = 10.00*0.04 = 0.40 -> sum = 10.40 -> round(10.40): paise ignored -> 10, already x10 -> 10
def test_golden_new_regime_immediately_above_rebate_boundary(new_rules):
    result = _calc(new_rules, gross_salary="1275010.00")
    assert result.taxable_income == Decimal("1200010")
    assert result.tax_before_rebate == Decimal("60001.50")
    assert result.rebate_amount == Decimal("59991.50")
    assert result.tax_after_rebate == Decimal("10.00")
    assert result.cess_amount == Decimal("0.40")
    assert result.total_tax_liability == Decimal("10")  # marginal relief caps tax at the excess-over-threshold


# --- Golden Case 6: old regime, exact Section 87A rebate boundary ---
# taxable_income target = 5,00,000 -> gross_salary = 5,00,000+50,000=5,50,000
# slabs: 0-2.5L:0; 2.5-5L@5%=12,500 => tax_before_rebate=12,500
# taxable<=threshold -> rebate=min(12500,12500)=12,500 -> tax_after=0; total=0
def test_golden_old_regime_exact_rebate_boundary(old_rules):
    result = _calc(old_rules, gross_salary="550000.00")
    assert result.taxable_income == Decimal("500000")
    assert result.tax_before_rebate == Decimal("12500.00")
    assert result.rebate_amount == Decimal("12500.00")
    assert result.total_tax_liability == Decimal("0")


# --- Golden Case 7: old regime, immediately ABOVE the rebate boundary (+10) — the "cliff" ---
# taxable_income target = 5,00,010 -> gross_salary = 5,00,010+50,000=5,50,010
# slabs: 0-2.5L:0; 2.5-5L@5%=12,500; 5L-500,010@20%=10*0.20=2.00 => tax_before_rebate=12,502.00
# old regime has NO marginal relief and taxable>threshold -> rebate=0
# cess = 12,502.00*0.04 = 500.08 -> sum=13,002.08 -> round: paise ignored->13,002; last digit 2<5 -> down to 13,000
def test_golden_old_regime_immediately_above_rebate_boundary_is_a_cliff(old_rules):
    result = _calc(old_rules, gross_salary="550010.00")
    assert result.taxable_income == Decimal("500010")
    assert result.tax_before_rebate == Decimal("12502.00")
    assert result.rebate_amount == Decimal("0.00")  # old regime: no marginal relief, confirmed hard cutoff
    assert result.tax_after_rebate == Decimal("12502.00")
    assert result.cess_amount == Decimal("500.08")
    assert result.total_tax_liability == Decimal("13000")


# --- Zero values ---
def test_golden_zero_income_produces_zero_tax_no_crash(new_rules):
    result = _calc(new_rules)
    assert result.gross_total_income == Decimal("0.00")
    assert result.taxable_income == Decimal("0")
    assert result.tax_before_rebate == Decimal("0.00")
    assert result.total_tax_liability == Decimal("0")
    assert result.net_payable == Decimal("0.00")


# --- Deduction eligibility: claimed > cap must not all be eligible ---
def test_section_80c_over_claim_is_capped_not_fully_eligible(old_rules):
    result = _calc(old_rules, gross_salary="1000000.00", deductions={"SECTION_80C": Decimal("200000.00")})
    assert result.total_deductions_applied == Decimal("150000.00")  # capped at 1,50,000, not the 2,00,000 claimed
    claimed_item = next(li for li in result.line_items if li.step_code == "SECTION_80C_CLAIMED")
    eligible_item = next(li for li in result.line_items if li.step_code == "SECTION_80C_ELIGIBLE")
    applied_item = next(li for li in result.line_items if li.step_code == "SECTION_80C_APPLIED")
    assert claimed_item.amount == Decimal("200000.00")
    assert eligible_item.amount == Decimal("150000.00")
    assert applied_item.amount == Decimal("150000.00")


# --- Regime-specific deduction eligibility: 80C claimed but regime is NEW ---
def test_section_80c_claim_has_no_effect_under_new_regime(new_rules):
    with_claim = _calc(new_rules, gross_salary="1000000.00", deductions={"SECTION_80C": Decimal("150000.00")})
    without_claim = _calc(new_rules, gross_salary="1000000.00")
    assert with_claim.total_tax_liability == without_claim.total_tax_liability
    eligible_item = next(li for li in with_claim.line_items if li.step_code == "SECTION_80C_ELIGIBLE")
    applied_item = next(li for li in with_claim.line_items if li.step_code == "SECTION_80C_APPLIED")
    assert eligible_item.amount == Decimal("0.00")
    assert applied_item.amount == Decimal("0.00")


def test_salary_plus_interest_income_aggregated(new_rules):
    result = _calc(new_rules, gross_salary="1000000.00", interest="50000.00")
    # income_from_salary = 1,000,000-75,000=925,000; + interest 50,000 = 975,000
    assert result.gross_total_income == Decimal("975000.00")


def test_surcharge_threshold_blocks_calculation_rather_than_understating_tax(new_rules):
    with pytest.raises(SurchargeNotSupportedError):
        _calc(new_rules, gross_salary="6000000.00")  # GTI 59,25,000 > Rs 50,00,000 threshold


def test_line_items_are_deterministic_and_ordered(new_rules):
    first = _calc(new_rules, gross_salary="1000000.00", tds="50000.00")
    second = _calc(new_rules, gross_salary="1000000.00", tds="50000.00")
    assert [li.step_code for li in first.line_items] == [li.step_code for li in second.line_items]
    assert [li.amount for li in first.line_items] == [li.amount for li in second.line_items]
    sequence_indices = [li.sequence_index for li in first.line_items]
    assert sequence_indices == sorted(sequence_indices)
    assert sequence_indices == list(range(1, len(sequence_indices) + 1))


def test_decimal_precision_never_uses_float():
    import inspect

    from app.engines.tax import calculation as calc_module

    source = inspect.getsource(calc_module)
    assert "float(" not in source
