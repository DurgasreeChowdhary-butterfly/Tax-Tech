"""Section 288A / 288B rounding boundary tests (app/engines/tax/rounding.py).
Rule (official, verified — see rounding.py docstring): ignore paise, then
round to the nearest multiple of ten (last digit >=5 rounds up, <5 rounds
down).
"""

from decimal import Decimal

import pytest

from app.engines.tax.rounding import round_to_nearest_ten


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0.00", "0"),
        ("10.00", "10"),
        ("12.99", "10"),  # paise ignored first -> 12 -> last digit 2 < 5 -> down to 10
        ("15.00", "20"),  # last digit 5 -> up
        ("14.99", "10"),  # paise ignored -> 14 -> down to 10
        ("925000.00", "925000"),  # already a multiple of ten
        ("925004.99", "925000"),
        ("925005.00", "925010"),
        ("13002.08", "13000"),  # from the old-regime cliff golden case
        ("60001.50", "60000"),
        ("5.00", "10"),  # last digit 5 with whole_rupees < 10
        ("4.99", "0"),
    ],
)
def test_round_to_nearest_ten_boundaries(raw, expected):
    assert round_to_nearest_ten(Decimal(raw)) == Decimal(expected)


def test_round_rejects_negative_amount():
    with pytest.raises(ValueError):
        round_to_nearest_ten(Decimal("-1.00"))
