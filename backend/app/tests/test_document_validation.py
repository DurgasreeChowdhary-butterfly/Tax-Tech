import pytest

from app.services.document_errors import UnsupportedFileTypeError
from app.services.document_validation import detect_content_type, sanitize_filename, validate_supported_content

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0mock jpeg content"
PNG_BYTES = b"\x89PNG\r\n\x1a\nmock png content"
TEXT_BYTES = b"just some plain text, not a real document"


def test_detect_content_type_for_supported_signatures():
    assert detect_content_type(PDF_BYTES) == "application/pdf"
    assert detect_content_type(JPEG_BYTES) == "image/jpeg"
    assert detect_content_type(PNG_BYTES) == "image/png"


def test_detect_content_type_returns_none_for_unsupported_content():
    assert detect_content_type(TEXT_BYTES) is None


def test_validate_supported_content_rejects_spoofed_extension_content():
    # Content-Type/extension are irrelevant here — only the actual bytes matter.
    with pytest.raises(UnsupportedFileTypeError):
        validate_supported_content(TEXT_BYTES)


def test_validate_supported_content_accepts_real_pdf_bytes():
    assert validate_supported_content(PDF_BYTES) == "application/pdf"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("form16.pdf", "form16.pdf"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\config.pdf", "config.pdf"),
        ("/etc/passwd", "passwd"),
        ("C:\\Users\\me\\form16.pdf", "form16.pdf"),
        ("weird<>name?.pdf", "weird__name_.pdf"),
        ("...pdf", "pdf"),
        ("", "file"),
    ],
)
def test_sanitize_filename_strips_path_components_and_unsafe_chars(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_long_names():
    long_name = "a" * 400 + ".pdf"
    result = sanitize_filename(long_name)
    assert len(result) <= 255
