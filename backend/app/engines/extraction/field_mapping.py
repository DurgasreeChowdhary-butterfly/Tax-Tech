from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable

from app.engines.extraction.errors import InvalidFieldValueError, UnsupportedFieldMappingError

_CURRENCY_MAX_DECIMALS = 2


def _validate_currency_string(field_name: str, value: object) -> Decimal:
    # Same rule as everywhere else in this codebase: money is a decimal
    # string, never a float, even for a raw candidate being verified.
    if not isinstance(value, str):
        raise InvalidFieldValueError(field_name, "expected a decimal amount as a string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidFieldValueError(field_name, "expected a decimal amount as a string") from exc
    if amount < 0:
        raise InvalidFieldValueError(field_name, "amount must not be negative")
    exponent = amount.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < -_CURRENCY_MAX_DECIMALS:
        raise InvalidFieldValueError(field_name, "amount must have at most 2 decimal places")
    return amount


def _validate_non_empty_text(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidFieldValueError(field_name, "expected a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class FieldMapping:
    domain_table: str  # "salary_income" | "interest_income"
    column: str
    _validator: Callable[[str, object], object]

    def validate(self, field_name: str, value: object) -> object:
        return self._validator(field_name, value)


# Deterministic, closed set — the ONLY field names Phase 7 can write into a
# domain record. `pan` is deliberately absent: PAN is protected taxpayer
# identity (docs/DATA_MODEL.md tax_profiles) and Phase 7 does not implement
# encryption, so confirming/correcting it must be rejected, not silently
# written anywhere in plaintext.
_FIELD_MAPPINGS: dict[str, FieldMapping] = {
    "employer_name": FieldMapping("salary_income", "employer_name", _validate_non_empty_text),
    "gross_salary": FieldMapping("salary_income", "gross_salary", _validate_currency_string),
    "tds_deducted": FieldMapping("salary_income", "tds_deducted", _validate_currency_string),
    "interest_amount": FieldMapping("interest_income", "interest_amount", _validate_currency_string),
}


def resolve_mapping(field_name: str) -> FieldMapping | None:
    return _FIELD_MAPPINGS.get(field_name)


def validate_mapped_value(field_name: str, value: object) -> tuple[FieldMapping, object]:
    """Resolve the field's domain mapping and validate `value` against it.

    Raises UnsupportedFieldMappingError if the field has no mapping at all
    (never writes to an arbitrary/unknown column), or InvalidFieldValueError
    if the value fails type/range validation for its mapped column.
    """
    mapping = resolve_mapping(field_name)
    if mapping is None:
        raise UnsupportedFieldMappingError(field_name)
    validated = mapping.validate(field_name, value)
    return mapping, validated
