from app.models.enums import FilerCategory, FilingSessionStatus, ResidencyStatus
from app.repositories.filing_session import create_filing_session, get_filing_session, update_filing_session
from app.repositories.tax_profile import create_tax_profile, get_tax_profile, update_tax_profile
from app.repositories.user import create_user, get_user, update_user
from app.repositories.user_profile import create_user_profile, get_user_profile, update_user_profile
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.schemas.tax_profile import TaxProfileCreate, TaxProfileUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.user_profile import UserProfileCreate, UserProfileUpdate


def test_user_repository_create_read_update(db_session):
    user = create_user(db_session, UserCreate(email="taxpayer@example.com"))

    fetched = get_user(db_session, user.id)
    assert fetched is not None
    assert fetched.email == "taxpayer@example.com"

    updated = update_user(db_session, fetched, UserUpdate(email="new@example.com"))
    assert updated.email == "new@example.com"


def test_user_profile_repository_create_read_update(db_session):
    user = create_user(db_session, UserCreate(email="taxpayer2@example.com"))

    profile = create_user_profile(db_session, UserProfileCreate(user_id=user.id, full_name="Priya Singh"))

    fetched = get_user_profile(db_session, profile.id)
    assert fetched is not None
    assert fetched.full_name == "Priya Singh"

    updated = update_user_profile(db_session, fetched, UserProfileUpdate(contact_number="9999999999"))
    assert updated.contact_number == "9999999999"


def test_tax_profile_repository_create_read_update(db_session):
    user = create_user(db_session, UserCreate(email="taxpayer3@example.com"))

    profile = create_tax_profile(db_session, TaxProfileCreate(user_id=user.id))

    fetched = get_tax_profile(db_session, profile.id)
    assert fetched is not None
    assert fetched.pan_encrypted is None

    updated = update_tax_profile(db_session, fetched, TaxProfileUpdate(pan_encrypted="ciphertext-placeholder"))
    assert updated.pan_encrypted == "ciphertext-placeholder"


def test_filing_session_repository_create_read_update(db_session):
    user = create_user(db_session, UserCreate(email="taxpayer4@example.com"))

    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    fetched = get_filing_session(db_session, session.id)
    assert fetched is not None
    assert fetched.status == FilingSessionStatus.IN_PROGRESS
    assert fetched.residency_status is None

    updated = update_filing_session(
        db_session,
        fetched,
        FilingSessionUpdate(
            status=FilingSessionStatus.COMPLETED,
            residency_status=ResidencyStatus.RESIDENT,
            filer_category=FilerCategory.SALARIED,
        ),
    )
    assert updated.status == FilingSessionStatus.COMPLETED
    assert updated.residency_status == ResidencyStatus.RESIDENT
    assert updated.filer_category == FilerCategory.SALARIED
