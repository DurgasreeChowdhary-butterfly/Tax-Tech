import uuid


class TaxEngineError(Exception):
    """Base class for tax engine domain errors."""


class PublishedRuleSetImmutableError(TaxEngineError):
    def __init__(self, rule_set_id: uuid.UUID):
        super().__init__(f"Tax rule set {rule_set_id} is published and immutable")
        self.rule_set_id = rule_set_id


class EmptyTaxRuleSetError(TaxEngineError):
    def __init__(self, rule_set_id: uuid.UUID):
        super().__init__(f"Tax rule set {rule_set_id} has no rules and cannot be published")
        self.rule_set_id = rule_set_id


class NoPublishedRuleSetError(TaxEngineError):
    """Raised when calculation is attempted for an assessment year with no
    PUBLISHED tax_rule_set — including when only a DRAFT rule set exists.
    Calculation must never fall back to a draft or a different assessment
    year's rule set."""

    def __init__(self, assessment_year: str):
        super().__init__(f"No published tax rule set for assessment year {assessment_year!r}")
        self.assessment_year = assessment_year


class MalformedRuleSetError(TaxEngineError):
    """A published rule set is missing a required rule/parameter the
    calculation engine needs. Never silently defaulted — calculation is
    refused outright rather than guessing a value."""

    def __init__(self, reason: str):
        super().__init__(f"Rule set is malformed for calculation: {reason}")
        self.reason = reason


class CaseNotSupportedForCalculationError(TaxEngineError):
    """The Supported Case Validator did not return SUPPORTED — calculation is
    refused. Only SUPPORTED cases receive a complete estimate
    (docs/TAX_ENGINE_BOUNDARY.md)."""

    def __init__(self, outcome: str):
        super().__init__(f"Filing session is not in a SUPPORTED state for calculation (outcome={outcome})")
        self.outcome = outcome


class SurchargeNotSupportedError(TaxEngineError):
    """Surcharge is not implemented in V1 (docs/TAX_ENGINE_BOUNDARY.md:
    "supported surcharge rules (only if explicitly implemented)"). Rather
    than silently omit surcharge and understate tax for high-income cases,
    calculation is refused outright above the officially documented first
    surcharge threshold (₹50,00,000 total income)."""

    def __init__(self, gross_total_income):
        super().__init__(
            f"Gross total income {gross_total_income} exceeds the surcharge threshold; "
            "surcharge is not implemented in V1 and calculation cannot proceed safely"
        )
        self.gross_total_income = gross_total_income


class UnsupportedDeductionCodeError(TaxEngineError):
    def __init__(self, code: str):
        super().__init__(f"Deduction code {code!r} is not supported")
        self.code = code


class InvalidDeductionValueError(TaxEngineError):
    def __init__(self, code: str, reason: str):
        super().__init__(f"Invalid claimed amount for deduction {code!r}: {reason}")
        self.code = code
        self.reason = reason
