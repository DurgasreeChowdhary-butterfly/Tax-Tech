from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.enums import FilerCategory, FilingComplexity, FilingSessionStatus, ResidencyStatus
from app.models.filing_session import FilingSession
from app.models.tax_profile import TaxProfile
from app.models.user import User
from app.models.user_profile import UserProfile


def _make_user(db_session, email: str = "user@example.com") -> User:
    user = User(email=email)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_user_profile_holds_general_details_only(db_session):
    user = _make_user(db_session)
    profile = UserProfile(user_id=user.id, full_name="Asha Rao", date_of_birth=date(1990, 1, 1))
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)

    assert user.profile.full_name == "Asha Rao"

    column_names = {c.name for c in UserProfile.__table__.columns}
    assert "pan_encrypted" not in column_names  # PAN lives in TaxProfile, not the general profile


def test_user_profile_is_one_to_one_per_user(db_session):
    user = _make_user(db_session)
    db_session.add(UserProfile(user_id=user.id))
    db_session.commit()

    db_session.add(UserProfile(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tax_profile_holds_protected_pan_and_is_one_to_one_per_user(db_session):
    user = _make_user(db_session)
    profile = TaxProfile(user_id=user.id, pan_encrypted="ciphertext-placeholder")
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(user)

    assert user.tax_profile.pan_encrypted == "ciphertext-placeholder"

    column_names = {c.name for c in TaxProfile.__table__.columns}
    assert "pan" not in column_names
    assert "pan_encrypted" in column_names
    assert "assessment_year" not in column_names  # not AY-scoped: stable identity, not a filing fact

    db_session.add(TaxProfile(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_filing_session_unique_per_user_and_assessment_year(db_session):
    user = _make_user(db_session)
    db_session.add(FilingSession(user_id=user.id, assessment_year="2026-27"))
    db_session.commit()

    db_session.add(FilingSession(user_id=user.id, assessment_year="2026-27"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_filing_session_defaults(db_session):
    user = _make_user(db_session)
    session = FilingSession(user_id=user.id, assessment_year="2026-27")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.status == FilingSessionStatus.IN_PROGRESS
    assert session.complexity == FilingComplexity.UNDETERMINED
    assert session.residency_status is None
    assert session.filer_category is None
    assert session.created_at is not None
    assert session.updated_at is not None


def test_filing_session_holds_assessment_year_specific_tax_context(db_session):
    user = _make_user(db_session)
    session = FilingSession(
        user_id=user.id,
        assessment_year="2026-27",
        residency_status=ResidencyStatus.RESIDENT,
        filer_category=FilerCategory.SALARIED,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.residency_status == ResidencyStatus.RESIDENT
    assert session.filer_category == FilerCategory.SALARIED

    # The same user can have a different residency/filer category in another
    # assessment year, since these are per-AY filing facts, not stable identity.
    other_year = FilingSession(
        user_id=user.id,
        assessment_year="2027-28",
        residency_status=ResidencyStatus.NON_RESIDENT,
    )
    db_session.add(other_year)
    db_session.commit()
    db_session.refresh(other_year)

    assert other_year.residency_status == ResidencyStatus.NON_RESIDENT


def test_filing_session_status_check_constraint_rejects_invalid_value(db_session):
    user = _make_user(db_session)
    session = FilingSession(user_id=user.id, assessment_year="2026-27")
    db_session.add(session)
    db_session.commit()

    # Raw SQL bypasses the ORM's Python-side enum validation so this exercises
    # the actual database CHECK constraint, not application-level validation.
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE filing_sessions SET status = 'NOT_A_REAL_STATUS' WHERE id = :id"),
            {"id": session.id.hex},
        )
    db_session.rollback()


def test_deleting_user_cascades_to_profiles_and_sessions(db_session):
    user = _make_user(db_session)
    db_session.add(UserProfile(user_id=user.id))
    db_session.add(TaxProfile(user_id=user.id))
    db_session.add(FilingSession(user_id=user.id, assessment_year="2026-27"))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(UserProfile).count() == 0
    assert db_session.query(TaxProfile).count() == 0
    assert db_session.query(FilingSession).count() == 0
