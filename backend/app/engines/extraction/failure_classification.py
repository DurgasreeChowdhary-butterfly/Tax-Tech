from app.integrations.ocr.base import ExtractionFailedError
from app.integrations.storage.base import StorageKeyError, StorageObjectNotFoundError
from app.models.enums import ExtractionFailureCode

# Fixed, safe messages only — never interpolate exception text, storage keys,
# file paths, or provider details into these. This is the ONLY thing exposed
# via the API for a failed job; the raw exception is kept separately
# (error_detail) for internal diagnostics only, never serialized in a schema.
_SAFE_MESSAGES = {
    ExtractionFailureCode.STORAGE_OBJECT_MISSING: "The source document could not be found in storage.",
    ExtractionFailureCode.STORAGE_ERROR: "A storage error occurred while processing the document.",
    ExtractionFailureCode.PROVIDER_ERROR: "The extraction provider failed to process the document.",
    ExtractionFailureCode.UNKNOWN_ERROR: "An unexpected error occurred while processing the document.",
}


def classify_failure(exc: Exception) -> ExtractionFailureCode:
    if isinstance(exc, StorageObjectNotFoundError):
        return ExtractionFailureCode.STORAGE_OBJECT_MISSING
    if isinstance(exc, StorageKeyError):
        return ExtractionFailureCode.STORAGE_ERROR
    if isinstance(exc, ExtractionFailedError):
        return ExtractionFailureCode.PROVIDER_ERROR
    return ExtractionFailureCode.UNKNOWN_ERROR


def safe_message_for(code: ExtractionFailureCode) -> str:
    return _SAFE_MESSAGES[code]


_MAX_DIAGNOSTIC_DETAIL_LENGTH = 100


def sanitize_diagnostic_detail(exc: Exception) -> str:
    """Bounded, allowlisted diagnostic context for operators (persisted in
    document_processing_jobs.error_detail).

    Returns only the exception's class name — a fixed identifier defined in
    code, never the exception message. Exception messages are unbounded and
    provider/library-controlled: they can and do embed storage keys, filing-
    session identifiers, filesystem paths, provider secrets/tokens, PAN,
    financial values, or document content (see docs/DATA_MODEL.md
    Sensitive-data notes). Never interpolate str(exc) here.
    """
    return type(exc).__name__[:_MAX_DIAGNOSTIC_DETAIL_LENGTH]
