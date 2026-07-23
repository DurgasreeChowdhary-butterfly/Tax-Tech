"""Parses persisted TaxRule rows (app/models/tax_rule.py) into typed,
Decimal-safe structures the calculation engine operates on. Never silently
defaults a missing/malformed parameter — raises MalformedRuleSetError instead,
so an incomplete or corrupted rule set blocks calculation rather than
producing a guessed number.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.engines.tax.errors import MalformedRuleSetError
from app.models.enums import TaxRuleType
from app.models.tax_rule import TaxRule


def _decimal(rule: TaxRule, key: str) -> Decimal:
    raw = rule.parameters.get(key)
    if raw is None:
        raise MalformedRuleSetError(f"rule {rule.code!r} ({rule.regime.value}) missing required parameter {key!r}")
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise MalformedRuleSetError(f"rule {rule.code!r} parameter {key!r} is not a valid decimal") from exc


def _optional_decimal(rule: TaxRule, key: str) -> Decimal | None:
    raw = rule.parameters.get(key)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise MalformedRuleSetError(f"rule {rule.code!r} parameter {key!r} is not a valid decimal") from exc


@dataclass(frozen=True)
class SlabRule:
    code: str
    min_amount: Decimal
    max_amount: Decimal | None  # None = no upper bound (top slab)
    rate: Decimal
    order_index: int


@dataclass(frozen=True)
class RebateRule:
    code: str
    threshold: Decimal
    max_rebate: Decimal
    marginal_relief: bool


@dataclass(frozen=True)
class CessRule:
    code: str
    rate: Decimal


@dataclass(frozen=True)
class StandardDeductionRule:
    code: str
    amount: Decimal


@dataclass(frozen=True)
class CappedDeductionRule:
    code: str
    cap: Decimal


def parse_slab_rules(rules: list[TaxRule]) -> list[SlabRule]:
    slabs = [
        SlabRule(
            code=r.code,
            min_amount=_decimal(r, "min"),
            max_amount=_optional_decimal(r, "max"),
            rate=_decimal(r, "rate"),
            order_index=r.order_index,
        )
        for r in rules
        if r.rule_type == TaxRuleType.SLAB
    ]
    if not slabs:
        raise MalformedRuleSetError("no SLAB rules found for this regime")
    return sorted(slabs, key=lambda s: s.order_index)


def parse_rebate_rule(rules: list[TaxRule]) -> RebateRule:
    matches = [r for r in rules if r.rule_type == TaxRuleType.REBATE]
    if not matches:
        raise MalformedRuleSetError("no REBATE rule found for this regime")
    rule = matches[0]
    marginal_relief_raw = rule.parameters.get("marginal_relief")
    if not isinstance(marginal_relief_raw, bool):
        raise MalformedRuleSetError(f"rule {rule.code!r} missing/invalid boolean parameter 'marginal_relief'")
    return RebateRule(
        code=rule.code,
        threshold=_decimal(rule, "threshold"),
        max_rebate=_decimal(rule, "max_rebate"),
        marginal_relief=marginal_relief_raw,
    )


def parse_cess_rule(rules: list[TaxRule]) -> CessRule:
    matches = [r for r in rules if r.rule_type == TaxRuleType.CESS]
    if not matches:
        raise MalformedRuleSetError("no CESS rule found for this regime")
    rule = matches[0]
    return CessRule(code=rule.code, rate=_decimal(rule, "rate"))


def parse_standard_deduction_rule(rules: list[TaxRule]) -> StandardDeductionRule:
    matches = [r for r in rules if r.rule_type == TaxRuleType.DEDUCTION and r.code == "STANDARD_DEDUCTION"]
    if not matches:
        raise MalformedRuleSetError("no STANDARD_DEDUCTION rule found for this regime")
    rule = matches[0]
    return StandardDeductionRule(code=rule.code, amount=_decimal(rule, "amount"))


def find_capped_deduction_rule(rules: list[TaxRule], code: str) -> CappedDeductionRule | None:
    """Returns None if this regime has no rule for `code` at all — the
    correct, deliberate representation of "not eligible in this regime"
    (e.g. SECTION_80C has no NEW-regime row)."""
    matches = [r for r in rules if r.rule_type == TaxRuleType.DEDUCTION and r.code == code]
    if not matches:
        return None
    rule = matches[0]
    return CappedDeductionRule(code=rule.code, cap=_decimal(rule, "cap"))
