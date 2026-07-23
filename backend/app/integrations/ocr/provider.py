from functools import lru_cache

from app.integrations.ocr.base import ExtractionProvider
from app.integrations.ocr.mock_provider import MockFormExtractionProvider


@lru_cache
def get_extraction_provider() -> ExtractionProvider:
    """Single seam for swapping OCR/AI backends. Only a deterministic mock
    exists today; a real OCR/AI provider can be added later by returning it
    here instead — no service/engine/domain code would need to change.
    """
    return MockFormExtractionProvider()
