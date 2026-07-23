import pytest
from sqlalchemy.exc import IntegrityError

from app.models.filing_flag import FilingFlag
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate


def test_filing_flag_unique_per_session_and_code(db_session):
    user = create_user(db_session, UserCreate(email="flags@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    db_session.add(FilingFlag(filing_session_id=session.id, flag_code="REVIEW_REQUIRED"))
    db_session.commit()

    db_session.add(FilingFlag(filing_session_id=session.id, flag_code="REVIEW_REQUIRED"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_filing_session_cascades_to_flags(db_session):
    user = create_user(db_session, UserCreate(email="flagscascade@example.com", password="TestPassword123!"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    db_session.add(FilingFlag(filing_session_id=session.id, flag_code="REVIEW_REQUIRED"))
    db_session.commit()

    db_session.delete(session)
    db_session.commit()

    assert db_session.query(FilingFlag).count() == 0
