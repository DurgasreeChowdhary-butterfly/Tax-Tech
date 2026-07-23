"""Pure, deterministic tax calculation for a single regime. No DB access here
— every input is already-loaded, already-verified data; the caller (service
layer) is responsible for enforcing the extraction-to-tax trust boundary
before this function is ever invoked.

Pipeline (docs/TAX_ENGINE_BOUNDARY.md), for one regime:
  gross salary -> less standard deduction -> income from salary
  + income from other sources (interest) -> gross total income
  - Chapter VI-A deduction claims (regime-eligible only) -> taxable income
  -> round (Section 288A) -> slab tax -> Section 87A rebate (+ marginal
  relief where officially applicable) -> cess -> total tax liability
  -> round (Section 288B) -> less verified TDS credit -> net payable/refund.

Only two rounding stages exist and both are statutory (Section 288A on
taxable income, Section 288B on final tax liability — see
app/engines/tax/rounding.py). Intermediate Decimal products (slab tax, cess)
are fixed to 2 decimal places (rupees-and-paise, matching the NUMERIC(14,2)
columns they are persisted into) using ROUND_HALF_UP purely as an engine-
internal precision choice — this is NOT a third statutory rounding stage.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.engines.tax.errors import SurchargeNotSupportedError
from app.engines.tax.rounding import round_to_nearest_ten
from app.engines.tax.rule_interpretation import (
    RebateRule,
    SlabRule,
    find_capped_deduction_rule,
    parse_cess_rule,
    parse_rebate_rule,
    parse_slab_rules,
    parse_standard_deduction_rule,
)
from app.models.tax_rule import TaxRule

_TWO_PLACES = Decimal("0.01")

# Bumped when the calculation LOGIC changes (not the rule content — that's
# tax_rule_set.engine_version). Distinct version axes let a same-inputs
# exact-retry stay idempotent while a bug fix to this code still forces a new
# tax_calculation version on next run (docs/TAX_ENGINE_BOUNDARY.md: "same
# inputs + same rule set version + same engine version = same output").
CALCULATION_ENGINE_VERSION = "v1"

# ₹50,00,000 — the first (lowest) official surcharge threshold, both regimes.
# Source (official, verified): incometax.gov.in "Salaried Individuals for
# AY 2026-27" surcharge table. Surcharge itself is NOT implemented in V1
# (docs/TAX_ENGINE_BOUNDARY.md: "supported surcharge rules (only if
# explicitly implemented)") — calculation is refused above this threshold
# rather than silently omitting surcharge and understating tax.
SURCHARGE_THRESHOLD = Decimal("5000000.00")


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineItem:
    step_code: str
    sequence_index: int
    amount: Decimal
    metadata: dict


@dataclass(frozen=True)
class CalculationResult:
    gross_total_income: Decimal
    total_deductions_applied: Decimal
    taxable_income: Decimal
    tax_before_rebate: Decimal
    rebate_amount: Decimal
    tax_after_rebate: Decimal
    cess_amount: Decimal
    total_tax_liability: Decimal
    total_tds_credit: Decimal
    net_payable: Decimal
    line_items: tuple[LineItem, ...]


def _apply_slabs(taxable_income: Decimal, slabs: list[SlabRule], emit) -> Decimal:
    total_tax = Decimal("0.00")
    for slab in slabs:
        if taxable_income <= slab.min_amount:
            continue
        upper = min(slab.max_amount, taxable_income) if slab.max_amount is not None else taxable_income
        amount_in_slab = upper - slab.min_amount
        if amount_in_slab <= 0:
            continue
        slab_tax = _q(amount_in_slab * slab.rate)
        emit(f"SLAB_TAX:{slab.code}", slab_tax, rule_code=slab.code, rate=str(slab.rate))
        total_tax += slab_tax
    return total_tax


def _compute_rebate(taxable_income: Decimal, tax_before_rebate: Decimal, rebate_rule: RebateRule) -> Decimal:
    if taxable_income <= rebate_rule.threshold:
        return min(tax_before_rebate, rebate_rule.max_rebate)
    if not rebate_rule.marginal_relief:
        return Decimal("0.00")
    excess = taxable_income - rebate_rule.threshold
    if tax_before_rebate > excess:
        return tax_before_rebate - excess
    return Decimal("0.00")


def calculate(
    *,
    rules: list[TaxRule],
    total_gross_salary: Decimal,
    total_tds_deducted: Decimal,
    total_interest_income: Decimal,
    deduction_claims: dict[str, Decimal],
) -> CalculationResult:
    slabs = parse_slab_rules(rules)
    rebate_rule = parse_rebate_rule(rules)
    cess_rule = parse_cess_rule(rules)
    std_ded_rule = parse_standard_deduction_rule(rules)

    line_items: list[LineItem] = []
    seq = 0

    def emit(step_code: str, amount: Decimal, **metadata) -> None:
        nonlocal seq
        seq += 1
        line_items.append(LineItem(step_code=step_code, sequence_index=seq, amount=amount, metadata=metadata))

    emit("GROSS_SALARY", total_gross_salary)
    standard_deduction_applied = min(std_ded_rule.amount, total_gross_salary)
    emit("STANDARD_DEDUCTION_APPLIED", standard_deduction_applied, rule_code=std_ded_rule.code)
    income_from_salary = total_gross_salary - standard_deduction_applied
    emit("INCOME_FROM_SALARY", income_from_salary)

    emit("INCOME_FROM_OTHER_SOURCES", total_interest_income)

    gross_total_income = income_from_salary + total_interest_income
    emit("GROSS_TOTAL_INCOME", gross_total_income)

    if gross_total_income > SURCHARGE_THRESHOLD:
        raise SurchargeNotSupportedError(gross_total_income)

    # V1 supports exactly one claimable deduction code (SECTION_80C) — see
    # app/engines/tax/deductions.py. With at most one claim, per-code
    # eligible/applied attribution below is exact; a second claimable
    # deduction would need proportional allocation against the aggregate
    # gross-total-income floor, which is deliberately not built until needed.
    eligible_by_code: dict[str, Decimal] = {}
    total_eligible = Decimal("0.00")
    for code, claimed_amount in sorted(deduction_claims.items()):
        capped_rule = find_capped_deduction_rule(rules, code)
        eligible = min(claimed_amount, capped_rule.cap) if capped_rule is not None else Decimal("0.00")
        eligible_by_code[code] = eligible
        total_eligible += eligible

    total_deductions_applied = min(total_eligible, gross_total_income)
    for code, claimed_amount in sorted(deduction_claims.items()):
        eligible = eligible_by_code[code]
        applied = min(eligible, total_deductions_applied)
        emit(f"{code}_CLAIMED", claimed_amount)
        emit(f"{code}_ELIGIBLE", eligible)
        emit(f"{code}_APPLIED", applied)

    emit("TOTAL_DEDUCTIONS_APPLIED", total_deductions_applied)

    taxable_income_before_rounding = max(Decimal("0.00"), gross_total_income - total_deductions_applied)
    taxable_income = round_to_nearest_ten(taxable_income_before_rounding)  # Section 288A
    emit("TAXABLE_INCOME", taxable_income)

    tax_before_rebate = _apply_slabs(taxable_income, slabs, emit)
    emit("TAX_BEFORE_REBATE", tax_before_rebate)

    rebate_amount = _compute_rebate(taxable_income, tax_before_rebate, rebate_rule)
    emit("REBATE_87A", rebate_amount, rule_code=rebate_rule.code)

    tax_after_rebate = tax_before_rebate - rebate_amount
    emit("TAX_AFTER_REBATE", tax_after_rebate)

    cess_amount = _q(tax_after_rebate * cess_rule.rate)
    emit("CESS", cess_amount, rule_code=cess_rule.code, rate=str(cess_rule.rate))

    total_tax_liability = round_to_nearest_ten(tax_after_rebate + cess_amount)  # Section 288B
    emit("TOTAL_TAX_LIABILITY", total_tax_liability)

    emit("TDS_CREDIT", total_tds_deducted)

    net_payable = total_tax_liability - total_tds_deducted
    emit("NET_PAYABLE", net_payable)

    return CalculationResult(
        gross_total_income=gross_total_income,
        total_deductions_applied=total_deductions_applied,
        taxable_income=taxable_income,
        tax_before_rebate=tax_before_rebate,
        rebate_amount=rebate_amount,
        tax_after_rebate=tax_after_rebate,
        cess_amount=cess_amount,
        total_tax_liability=total_tax_liability,
        total_tds_credit=total_tds_deducted,
        net_payable=net_payable,
        line_items=tuple(line_items),
    )
