from decimal import Decimal

import pytest

from app.engines.tax.errors import MalformedRuleSetError
from app.engines.tax.rule_interpretation import (
    find_capped_deduction_rule,
    parse_cess_rule,
    parse_rebate_rule,
    parse_slab_rules,
    parse_standard_deduction_rule,
)
from app.models.enums import TaxRegime, TaxRuleType
from app.models.tax_rule import TaxRule


def _rule(regime, rule_type, code, order_index=1, **parameters):
    return TaxRule(regime=regime, rule_type=rule_type, code=code, order_index=order_index, parameters=parameters)


def test_parse_slab_rules_sorted_by_order_index():
    rules = [
        _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_2", order_index=2, min="100.00", max="200.00", rate="0.05"),
        _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_1", order_index=1, min="0.00", max="100.00", rate="0.00"),
    ]
    slabs = parse_slab_rules(rules)
    assert [s.code for s in slabs] == ["SLAB_1", "SLAB_2"]
    assert slabs[1].max_amount == Decimal("200.00")


def test_parse_slab_rules_top_slab_has_no_max():
    rules = [_rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_1", min="0.00", max=None, rate="0.30")]
    slabs = parse_slab_rules(rules)
    assert slabs[0].max_amount is None


def test_parse_slab_rules_empty_raises():
    with pytest.raises(MalformedRuleSetError):
        parse_slab_rules([])


def test_parse_slab_rule_missing_parameter_raises():
    bad_rule = TaxRule(regime=TaxRegime.NEW, rule_type=TaxRuleType.SLAB, code="SLAB_1", order_index=1, parameters={"min": "0.00"})
    with pytest.raises(MalformedRuleSetError):
        parse_slab_rules([bad_rule])


def test_parse_rebate_rule_requires_marginal_relief_boolean():
    rules = [_rule(TaxRegime.NEW, TaxRuleType.REBATE, "SECTION_87A", threshold="1200000.00", max_rebate="60000.00")]
    with pytest.raises(MalformedRuleSetError):
        parse_rebate_rule(rules)


def test_parse_rebate_rule_success():
    rules = [
        _rule(
            TaxRegime.NEW, TaxRuleType.REBATE, "SECTION_87A",
            threshold="1200000.00", max_rebate="60000.00", marginal_relief=True,
        )
    ]
    rebate = parse_rebate_rule(rules)
    assert rebate.threshold == Decimal("1200000.00")
    assert rebate.marginal_relief is True


def test_parse_cess_rule_missing_raises():
    with pytest.raises(MalformedRuleSetError):
        parse_cess_rule([])


def test_parse_standard_deduction_rule_missing_raises():
    with pytest.raises(MalformedRuleSetError):
        parse_standard_deduction_rule([])


def test_find_capped_deduction_rule_absent_returns_none():
    rules = [_rule(TaxRegime.OLD, TaxRuleType.DEDUCTION, "SECTION_80C", cap="150000.00")]
    assert find_capped_deduction_rule(rules, "SECTION_80C") is not None
    assert find_capped_deduction_rule(rules, "SECTION_NOT_PRESENT") is None
