import uuid


class ExtractionError(Exception):
    """Base class for extraction engine/service domain errors."""


class DocumentProcessingJobNotFoundError(ExtractionError):
    def __init__(self, job_id: uuid.UUID):
        super().__init__(f"Document processing job {job_id} not found")
        self.job_id = job_id


class NoExtractionAvailableError(ExtractionError):
    def __init__(self, tax_document_id: uuid.UUID):
        super().__init__(f"No completed extraction available for document {tax_document_id}")
        self.tax_document_id = tax_document_id


class UnsupportedFieldMappingError(ExtractionError):
    """Raised when a field has no documented, deterministic mapping to a
    verified domain record. Includes protected fields (e.g. `pan`), which are
    deliberately never mapped here — see docs/DATA_MODEL.md's tax_profiles
    protected-identity boundary; Phase 7 does not implement PAN encryption, so
    it must not write a plaintext PAN anywhere via this workflow.
    """

    def __init__(self, field_name: str):
        super().__init__(f"Extracted field {field_name!r} has no supported domain mapping")
        self.field_name = field_name


class InvalidFieldValueError(ExtractionError):
    def __init__(self, field_name: str, reason: str):
        super().__init__(f"Invalid value for field {field_name!r}: {reason}")
        self.field_name = field_name
        self.reason = reason
