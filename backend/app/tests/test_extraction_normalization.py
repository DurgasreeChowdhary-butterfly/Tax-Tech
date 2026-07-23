from app.engines.extraction.normalization import normalize_field_candidates
from app.integrations.ocr.base import FieldCandidate


def test_normalize_trims_whitespace_from_strings_and_names():
    fields = [FieldCandidate(field_name="  employer_name ", value="  ACME CORP  ", confidence=0.9)]

    normalized = normalize_field_candidates(fields)

    assert normalized[0].field_name == "employer_name"
    assert normalized[0].value == "ACME CORP"


def test_normalize_clamps_confidence_into_valid_range():
    fields = [
        FieldCandidate(field_name="a", value="x", confidence=1.5),
        FieldCandidate(field_name="b", value="y", confidence=-0.2),
    ]

    normalized = normalize_field_candidates(fields)

    assert normalized[0].confidence == 1.0
    assert normalized[1].confidence == 0.0


def test_normalize_leaves_non_string_values_untouched():
    fields = [FieldCandidate(field_name="count", value=3, confidence=0.5)]

    normalized = normalize_field_candidates(fields)

    assert normalized[0].value == 3
