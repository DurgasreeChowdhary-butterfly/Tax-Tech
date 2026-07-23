import uuid


class DocumentError(Exception):
    """Base class for document service domain errors."""


class DocumentNotFoundError(DocumentError):
    def __init__(self, document_id: uuid.UUID, filing_session_id: uuid.UUID):
        super().__init__(f"Document {document_id} not found for filing session {filing_session_id}")
        self.document_id = document_id
        self.filing_session_id = filing_session_id


class EmptyFileError(DocumentError):
    def __init__(self):
        super().__init__("Uploaded file is empty")


class FileTooLargeError(DocumentError):
    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(f"File size {size_bytes} exceeds the maximum allowed size of {max_bytes} bytes")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class UnsupportedFileTypeError(DocumentError):
    def __init__(self, reason: str):
        super().__init__(f"Unsupported file type: {reason}")
        self.reason = reason


class StorageObjectMissingError(DocumentError):
    """The DB says this document exists, but its backing storage object does not."""

    def __init__(self, document_id: uuid.UUID):
        super().__init__(f"Storage object for document {document_id} is missing")
        self.document_id = document_id
