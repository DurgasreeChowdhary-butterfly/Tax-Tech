from decimal import Decimal

import pytest

from app.engines.tax.deductions import validate_deduction_claim
from app.engines.tax.errors import InvalidDeductionValueError, UnsupportedDeductionCodeError


def test_supported_deduction_code_validates():
    assert validate_deduction_claim("SECTION_80C", "150000.00") == Decimal("150000.00")


def test_unsupported_deduction_code_rejected():
    with pytest.raises(UnsupportedDeductionCodeError):
        validate_deduction_claim("SECTION_80D", "10000.00")


@pytest.mark.parametrize(
    "claimed_amount",
    [150000.00, "not-a-number", "-1.00", "100.999", None, 150000],
)
def test_invalid_claimed_values_rejected(claimed_amount):
    with pytest.raises(InvalidDeductionValueError):
        validate_deduction_claim("SECTION_80C", claimed_amount)
