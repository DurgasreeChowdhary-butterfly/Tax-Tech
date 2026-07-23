from app.integrations.ocr.base import ExtractionResult, FieldCandidate

PROVIDER_VERSION = "mock-form16-v1"

# Deterministic stand-in for a real OCR/AI provider. Always returns the same
# Form16-shaped candidate fields regardless of actual document content —
# proving the pipeline mechanics (job -> extraction -> fields), not real
# document understanding. A real provider is a future adapter behind the same
# ExtractionProvider interface.
_MOCK_FIELDS = (
    FieldCandidate(field_name="employer_name", value="MOCK EMPLOYER PVT LTD", confidence=0.95),
    FieldCandidate(field_name="pan", value="AAAPZ9999Z", confidence=0.90),
    FieldCandidate(field_name="gross_salary", value="1200000.00", confidence=0.85),
    FieldCandidate(field_name="tds_deducted", value="95000.00", confidence=0.80),
)


class MockFormExtractionProvider:
    """Deterministic mock adapter. See ExtractionProvider (base.py)."""

    def extract(self, content: bytes, content_type: str) -> ExtractionResult:
        fields = list(_MOCK_FIELDS)
        raw_output = {
            "provider": "MOCK",
            "provider_version": PROVIDER_VERSION,
            "content_type": content_type,
            "source_size_bytes": len(content),
            "fields": [{"field_name": f.field_name, "value": f.value, "confidence": f.confidence} for f in fields],
        }
        return ExtractionResult(provider_version=PROVIDER_VERSION, raw_output=raw_output, fields=fields)
