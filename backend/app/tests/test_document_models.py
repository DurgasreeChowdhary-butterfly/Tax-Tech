import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import DocumentStatus, StorageProviderName
from app.models.tax_document import TaxDocument
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate


def _make_session(db_session, email):
    user = create_user(db_session, UserCreate(email=email, password="TestPassword123!"))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def _document(session_id, storage_key, content_hash, status=DocumentStatus.UPLOADED):
    return TaxDocument(
        id=uuid.uuid4(),
        filing_session_id=session_id,
        original_filename="a.pdf",
        storage_key=storage_key,
        storage_provider=StorageProviderName.LOCAL_FILESYSTEM,
        content_type="application/pdf",
        size_bytes=10,
        content_hash=content_hash,
        status=status,
    )


def test_duplicate_active_hash_rejected_at_db_level(db_session):
    session = _make_session(db_session, "dbcheck@example.com")
    db_session.add(_document(session.id, "k1", "hash-a"))
    db_session.commit()

    db_session.add(_document(session.id, "k2", "hash-a"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_hash_allowed_when_original_deleted(db_session):
    session = _make_session(db_session, "dbcheck2@example.com")
    db_session.add(_document(session.id, "k1", "hash-a", status=DocumentStatus.DELETED))
    db_session.commit()

    db_session.add(_document(session.id, "k2", "hash-a", status=DocumentStatus.UPLOADED))
    db_session.commit()  # must not raise — the earlier row is DELETED


def test_storage_key_must_be_globally_unique(db_session):
    session = _make_session(db_session, "keyunique@example.com")
    db_session.add(_document(session.id, "same-key", "hash-a"))
    db_session.commit()

    db_session.add(_document(session.id, "same-key", "hash-b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_size_must_be_positive_at_db_level(db_session):
    session = _make_session(db_session, "sizecheck@example.com")
    doc = _document(session.id, "k1", "hash-a")
    doc.size_bytes = 0
    db_session.add(doc)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_filing_session_cascades_to_documents(db_session):
    session = _make_session(db_session, "cascade@example.com")
    db_session.add(_document(session.id, "k1", "hash-a"))
    db_session.commit()

    db_session.delete(session)
    db_session.commit()

    assert db_session.query(TaxDocument).count() == 0
