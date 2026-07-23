from app.integrations.ocr.mock_provider import MockFormExtractionProvider


def test_mock_provider_produces_deterministic_form16_like_fields():
    provider = MockFormExtractionProvider()

    result_a = provider.extract(b"pdf bytes one", "application/pdf")
    result_b = provider.extract(b"completely different bytes", "application/pdf")

    field_names_a = {f.field_name for f in result_a.fields}
    field_names_b = {f.field_name for f in result_b.fields}
    assert field_names_a == field_names_b == {"employer_name", "pan", "gross_salary", "tds_deducted"}
    assert all(0.0 <= f.confidence <= 1.0 for f in result_a.fields)
    assert result_a.provider_version == result_b.provider_version


def test_mock_provider_raw_output_reflects_input_size():
    provider = MockFormExtractionProvider()
    result = provider.extract(b"12345", "application/pdf")

    assert result.raw_output["source_size_bytes"] == 5
    assert result.raw_output["content_type"] == "application/pdf"
