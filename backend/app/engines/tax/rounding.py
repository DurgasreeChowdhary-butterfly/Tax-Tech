"""Rounding under the Income Tax Act, 1961.

Section 288A ("Rounding off of income") and Section 288B ("Rounding off
amount payable and refund due") both prescribe the identical rule: any paise
are ignored, and the resulting whole-rupee amount is rounded to the nearest
multiple of ten (round up if the last digit is 5 or more, round down
otherwise). Source (official, verified): Income Tax Department bare-act text
for these two sections, https://www.incometaxindia.gov.in (Section 288A /
Section 288B), cross-confirmed via indiankanoon.org's and kanoongpt.in's
verbatim mirrors of the same statute where the department's own pages could
not be fetched directly (blocked to automated requests). No other rounding
behaviour (e.g. rounding each intermediate line item) is invented — only
these two explicit statutory stages are applied, at the two points documented
in the calculation pipeline (docs/TAX_ENGINE_BOUNDARY.md): once on taxable
income (288A) and once on the final tax liability (288B).
"""

from decimal import ROUND_DOWN, Decimal


def round_to_nearest_ten(amount: Decimal) -> Decimal:
    if amount < 0:
        raise ValueError("amount to round must not be negative")

    whole_rupees = amount.to_integral_value(rounding=ROUND_DOWN)  # ignore paise
    remainder = whole_rupees % 10
    if remainder == 0:
        return whole_rupees
    if remainder >= 5:
        return whole_rupees + (10 - remainder)
    return whole_rupees - remainder
