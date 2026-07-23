import re
from pathlib import PurePosixPath

from app.services.document_errors import UnsupportedFileTypeError

# Signature-based detection only — never trust a client-supplied Content-Type
# or filename extension. Kept to the small set of formats this product
# actually needs (Form 16-style scans/PDFs); extend deliberately, not by
# trusting caller-supplied hints.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9 ._-]")
_MAX_FILENAME_LENGTH = 255


def detect_content_type(content: bytes) -> str | None:
    """Sniff the real file type from its magic bytes. Returns None if it
    doesn't match any supported signature."""
    for signature, content_type in _SIGNATURES:
        if content.startswith(signature):
            return content_type
    return None


def validate_supported_content(content: bytes) -> str:
    """Detect and validate the file's real type. Raises UnsupportedFileTypeError
    if the content doesn't match a supported signature — regardless of what
    Content-Type or filename extension the client sent."""
    content_type = detect_content_type(content)
    if content_type is None:
        raise UnsupportedFileTypeError("file content does not match a supported format (PDF, JPEG, PNG)")
    return content_type


def sanitize_filename(filename: str) -> str:
    """Normalize a client-supplied filename into safe display metadata only.
    Never used to construct a storage path — see storage_key generation in
    app/services/document.py.
    """
    # Strip any path components the client might have sent (path traversal
    # attempt or just a browser sending a full path) — keep only the leaf name.
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = _SAFE_FILENAME_CHARS.sub("_", name).strip()
    name = name.lstrip(".") or "file"
    return name[:_MAX_FILENAME_LENGTH]
