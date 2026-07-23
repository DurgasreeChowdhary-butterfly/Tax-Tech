import uuid

import pytest

from app.models.enums import DocumentStatus
from app.repositories import tax_document as tax_document_repo
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.services import document as document_service
from app.services.document_errors import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
    StorageObjectMissingError,
    UnsupportedFileTypeError,
)

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for tests\n"


def _make_session(db_session, email):
    user = create_user(db_session, UserCreate(email=email, password="TestPassword123!"))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def test_successful_upload_persists_metadata_and_storage_object(db_session, document_storage):
    session = _make_session(db_session, "upload@example.com")

    document, is_duplicate = document_service.upload_document(
        db_session, session.id, original_filename="form16.pdf", content=PDF_BYTES, storage=document_storage
    )

    assert is_duplicate is False
    assert document.content_type == "application/pdf"
    assert document.size_bytes == len(PDF_BYTES)
    assert document.status == DocumentStatus.UPLOADED
    assert document_storage.exists(document.storage_key) is True
    assert document_storage.read(document.storage_key) == PDF_BYTES


def test_storage_key_is_server_generated_not_derived_from_filename(db_session, document_storage):
    session = _make_session(db_session, "keygen@example.com")

    document, _ = document_service.upload_document(
        db_session, session.id, original_filename="my-secret-form16.pdf", content=PDF_BYTES, storage=document_storage
    )

    assert "my-secret-form16" not in document.storage_key
    assert str(document.id) in document.storage_key
    assert str(session.id) in document.storage_key


def test_original_filename_cannot_control_storage_path(db_session, document_storage):
    session = _make_session(db_session, "traversal-filename@example.com")

    document, _ = document_service.upload_document(
        db_session, session.id, original_filename="../../etc/passwd", content=PDF_BYTES, storage=document_storage
    )

    assert document.original_filename == "passwd"  # sanitized display metadata only
    assert ".." not in document.storage_key
    # The file landed inside the session's own directory, nowhere else.
    assert document.storage_key.startswith(f"filing-sessions/{session.id}/")


def test_mime_spoofing_is_rejected(db_session, document_storage):
    session = _make_session(db_session, "spoof@example.com")

    with pytest.raises(UnsupportedFileTypeError):
        document_service.upload_document(
            db_session,
            session.id,
            original_filename="innocent.pdf",  # extension lies
            content=b"just plain text pretending to be a pdf",
            storage=document_storage,
        )


def test_empty_file_is_rejected(db_session, document_storage):
    session = _make_session(db_session, "empty@example.com")

    with pytest.raises(EmptyFileError):
        document_service.upload_document(
            db_session, session.id, original_filename="empty.pdf", content=b"", storage=document_storage
        )


def test_oversized_file_is_rejected(db_session, document_storage, monkeypatch):
    session = _make_session(db_session, "oversize@example.com")

    class TinyLimitSettings:
        max_upload_size_bytes = 10

    monkeypatch.setattr("app.services.document.get_settings", lambda: TinyLimitSettings())

    with pytest.raises(FileTooLargeError):
        document_service.upload_document(
            db_session, session.id, original_filename="big.pdf", content=PDF_BYTES, storage=document_storage
        )


def test_duplicate_content_is_idempotent(db_session, document_storage):
    session = _make_session(db_session, "dup@example.com")

    first, first_is_dup = document_service.upload_document(
        db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
    )
    second, second_is_dup = document_service.upload_document(
        db_session, session.id, original_filename="b.pdf", content=PDF_BYTES, storage=document_storage
    )

    assert first_is_dup is False
    assert second_is_dup is True
    assert first.id == second.id  # no new row
    assert len(tax_document_repo.list_documents(db_session, session.id)) == 1


def test_duplicate_after_deletion_is_allowed_again(db_session, document_storage):
    session = _make_session(db_session, "dup-after-delete@example.com")

    first, _ = document_service.upload_document(
        db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
    )
    document_service.delete_document(db_session, session.id, first.id, storage=document_storage)

    second, is_duplicate = document_service.upload_document(
        db_session, session.id, original_filename="a-again.pdf", content=PDF_BYTES, storage=document_storage
    )

    assert is_duplicate is False  # original was deleted, so this is a fresh upload
    assert second.id != first.id


def test_cross_session_access_is_rejected(db_session, document_storage):
    session_a = _make_session(db_session, "cross-a@example.com")
    session_b = _make_session(db_session, "cross-b@example.com")

    document, _ = document_service.upload_document(
        db_session, session_a.id, original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
    )

    with pytest.raises(DocumentNotFoundError):
        document_service.get_document(db_session, session_b.id, document.id)

    with pytest.raises(DocumentNotFoundError):
        document_service.get_document_content(db_session, session_b.id, document.id, storage=document_storage)

    with pytest.raises(DocumentNotFoundError):
        document_service.delete_document(db_session, session_b.id, document.id, storage=document_storage)


def test_missing_storage_object_is_detected(db_session, document_storage):
    session = _make_session(db_session, "missing-object@example.com")

    document, _ = document_service.upload_document(
        db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
    )
    # Simulate the file vanishing from storage without going through the service
    # (disk corruption, manual intervention, etc.) — the DB still says UPLOADED.
    document_storage.delete(document.storage_key)

    with pytest.raises(StorageObjectMissingError):
        document_service.get_document_content(db_session, session.id, document.id, storage=document_storage)


def test_storage_failure_creates_no_document_record(db_session, document_storage):
    session = _make_session(db_session, "storage-fail@example.com")

    class FailingStorage:
        def save(self, key, content):
            raise OSError("disk full")

        def read(self, key):
            raise AssertionError("should not be called")

        def exists(self, key):
            return False

        def delete(self, key):
            raise AssertionError("should not be called")

    with pytest.raises(OSError):
        document_service.upload_document(
            db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=FailingStorage()
        )

    assert tax_document_repo.list_documents(db_session, session.id) == []


def test_db_failure_after_storage_write_triggers_cleanup(db_session, document_storage, monkeypatch):
    session = _make_session(db_session, "db-fail@example.com")

    saved_keys: list[str] = []
    deleted_keys: list[str] = []

    class RecordingStorage:
        def save(self, key, content):
            document_storage.save(key, content)
            saved_keys.append(key)

        def read(self, key):
            return document_storage.read(key)

        def exists(self, key):
            return document_storage.exists(key)

        def delete(self, key):
            document_storage.delete(key)
            deleted_keys.append(key)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(tax_document_repo, "create_document", _boom)

    with pytest.raises(RuntimeError):
        document_service.upload_document(
            db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=RecordingStorage()
        )

    assert tax_document_repo.list_documents(db_session, session.id) == []
    assert len(saved_keys) == 1
    assert deleted_keys == saved_keys  # the orphaned object was cleaned up
    assert document_storage.exists(saved_keys[0]) is False


def test_document_lifecycle_delete_is_explicit_and_idempotent(db_session, document_storage):
    session = _make_session(db_session, "lifecycle@example.com")

    document, _ = document_service.upload_document(
        db_session, session.id, original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
    )
    assert document_storage.exists(document.storage_key) is True

    deleted = document_service.delete_document(db_session, session.id, document.id, storage=document_storage)
    assert deleted.status == DocumentStatus.DELETED
    assert deleted.deleted_at is not None
    assert document_storage.exists(document.storage_key) is False

    # Deleted documents are no longer retrievable via the normal fetch path...
    with pytest.raises(DocumentNotFoundError):
        document_service.get_document(db_session, session.id, document.id)

    # ...but repeated deletion is a safe no-op, not an error.
    deleted_again = document_service.delete_document(db_session, session.id, document.id, storage=document_storage)
    assert deleted_again.status == DocumentStatus.DELETED


def test_unknown_filing_session_is_rejected(db_session, document_storage):
    with pytest.raises(ValueError):
        document_service.upload_document(
            db_session, uuid.uuid4(), original_filename="a.pdf", content=PDF_BYTES, storage=document_storage
        )
