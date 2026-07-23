import uuid


class VerificationError(Exception):
    """Base class for verification service domain errors."""


class ExtractedFieldNotFoundError(VerificationError):
    def __init__(self, field_id: uuid.UUID):
        super().__init__(f"Extracted field {field_id} not found for this document")
        self.field_id = field_id


class MissingCorrectionValueError(VerificationError):
    def __init__(self):
        super().__init__("A CORRECT action requires a value")
