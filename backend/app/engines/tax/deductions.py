"""Closed vocabulary of claimable deductions for V1 and their claim-value
validation. A deduction claim is direct manual entry (like salary_income can
be "confirmed Form16 extraction or manual entry" per its docstring) — there
is no extraction candidate for a deduction claim in V1, so no verification
workflow is needed; the claim itself is the verified input.

Only Section 80C is implemented for V1 (docs/PRODUCT_SCOPE.md: "Explicitly
implemented deduction rules... not an open-ended list"). Source (official,
verified): https://www.incometaxindia.gov.in/w/section-80c and
https://www.incometaxindia.gov.in/w/deductions — cap of Rs. 1,50,000
(technically an aggregate ceiling shared with sections 80CCC/80CCD(1) under
section 80CCE; V1 models Section 80C alone as a deliberate scope
simplification, not an accuracy claim about the combined ceiling). Old
regime only: new tax regime disallows Chapter VI-A deductions except
80CCD(2)/80CCH/80JJAA (https://www.incometax.gov.in/iec/foportal/help/new-tax-vs-old-tax-regime-faqs),
none of which are implemented in V1.
"""

from decimal import Decimal, InvalidOperation

from app.engines.tax.errors import InvalidDeductionValueError, UnsupportedDeductionCodeError

SUPPORTED_DEDUCTION_CODES = frozenset({"SECTION_80C"})

_MAX_DECIMALS = 2


def validate_deduction_claim(code: str, claimed_amount: object) -> Decimal:
    if code not in SUPPORTED_DEDUCTION_CODES:
        raise UnsupportedDeductionCodeError(code)
    if not isinstance(claimed_amount, str):
        raise InvalidDeductionValueError(code, "expected a decimal amount as a string")
    try:
        amount = Decimal(claimed_amount)
    except InvalidOperation as exc:
        raise InvalidDeductionValueError(code, "expected a decimal amount as a string") from exc
    if amount < 0:
        raise InvalidDeductionValueError(code, "amount must not be negative")
    exponent = amount.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < -_MAX_DECIMALS:
        raise InvalidDeductionValueError(code, "amount must have at most 2 decimal places")
    return amount
