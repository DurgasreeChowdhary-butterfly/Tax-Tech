from dataclasses import dataclass
from typing import Protocol


class ExtractionFailedError(Exception):
    """Raised by a provider when it cannot produce an extraction for the given
    content. Distinct from a bug/crash — this is an expected, handled outcome
    (the worker records it on the job as FAILED, nothing else)."""


@dataclass(frozen=True)
class FieldCandidate:
    field_name: str
    value: object
    confidence: float


@dataclass(frozen=True)
class ExtractionResult:
    provider_version: str
    raw_output: dict
    fields: list[FieldCandidate]


class ExtractionProvider(Protocol):
    """OCR/AI adapter abstraction. Extraction assistance only — see
    docs/TAX_ENGINE_BOUNDARY.md: raw output from here never reaches a tax
    calculation or domain table directly. Only one implementation exists today
    (a deterministic mock); a real OCR/AI provider is a future adapter behind
    this same interface.
    """

    def extract(self, content: bytes, content_type: str) -> ExtractionResult: ...
