from app.integrations.ocr.base import FieldCandidate

# Pure, deterministic step between raw adapter output and persistence — the
# "normalization" stage of the documented boundary
# (docs/TAX_ENGINE_BOUNDARY.md: Document -> ... -> extraction record ->
# normalization -> ...). Confidence/range validation and user confirmation
# into a verified domain record remain later stages (Phase 7+), not this one.


def normalize_field_candidates(fields: list[FieldCandidate]) -> list[FieldCandidate]:
    normalized = []
    for field in fields:
        value = field.value.strip() if isinstance(field.value, str) else field.value
        confidence = max(0.0, min(1.0, float(field.confidence)))
        normalized.append(FieldCandidate(field_name=field.field_name.strip(), value=value, confidence=confidence))
    return normalized
