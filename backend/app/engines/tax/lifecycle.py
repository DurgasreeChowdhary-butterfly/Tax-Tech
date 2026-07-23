from app.engines.tax.errors import EmptyTaxRuleSetError, PublishedRuleSetImmutableError
from app.models.enums import TaxRuleSetStatus
from app.models.tax_rule_set import TaxRuleSet


def validate_draft(rule_set: TaxRuleSet) -> None:
    """Guard for any write to a rule set's tax_rules."""
    if rule_set.status == TaxRuleSetStatus.PUBLISHED:
        raise PublishedRuleSetImmutableError(rule_set.id)


def validate_publishable(rule_set: TaxRuleSet) -> None:
    if rule_set.status == TaxRuleSetStatus.PUBLISHED:
        raise PublishedRuleSetImmutableError(rule_set.id)
    if not rule_set.tax_rules:
        raise EmptyTaxRuleSetError(rule_set.id)
