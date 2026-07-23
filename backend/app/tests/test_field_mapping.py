import pytest

from app.engines.extraction.errors import InvalidFieldValueError, UnsupportedFieldMappingError
from app.engines.extraction.field_mapping import resolve_mapping, validate_mapped_value


def test_supported_fields_resolve_to_expected_domain_column():
    assert resolve_mapping("employer_name").domain_table == "salary_income"
    assert resolve_mapping("gross_salary").domain_table == "salary_income"
    assert resolve_mapping("tds_deducted").domain_table == "salary_income"
    assert resolve_mapping("interest_amount").domain_table == "interest_income"


def test_pan_and_unknown_fields_are_unsupported():
    assert resolve_mapping("pan") is None
    assert resolve_mapping("some_made_up_field") is None

    with pytest.raises(UnsupportedFieldMappingError):
        validate_mapped_value("pan", "AAAPZ9999Z")
    with pytest.raises(UnsupportedFieldMappingError):
        validate_mapped_value("some_made_up_field", "whatever")


def test_currency_field_validates_decimal_string():
    mapping, value = validate_mapped_value("gross_salary", "1200000.00")
    assert mapping.column == "gross_salary"
    assert str(value) == "1200000.00"


@pytest.mark.parametrize(
    "bad_value",
    [
        1200000.00,  # float rejected outright, even if numerically fine
        "not-a-number",
        "-500.00",
        "100.999",
        None,
        123,
    ],
)
def test_currency_field_rejects_invalid_values(bad_value):
    with pytest.raises(InvalidFieldValueError):
        validate_mapped_value("gross_salary", bad_value)


def test_text_field_rejects_empty_or_non_string():
    with pytest.raises(InvalidFieldValueError):
        validate_mapped_value("employer_name", "   ")
    with pytest.raises(InvalidFieldValueError):
        validate_mapped_value("employer_name", 123)


def test_text_field_strips_whitespace():
    _mapping, value = validate_mapped_value("employer_name", "  ACME CORP  ")
    assert value == "ACME CORP"
