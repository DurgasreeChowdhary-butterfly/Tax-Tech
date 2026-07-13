import uuid

from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile
from app.schemas.user_profile import UserProfileCreate, UserProfileUpdate


def create_user_profile(db: Session, data: UserProfileCreate) -> UserProfile:
    profile = UserProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_user_profile(db: Session, profile_id: uuid.UUID) -> UserProfile | None:
    return db.get(UserProfile, profile_id)


def update_user_profile(db: Session, profile: UserProfile, data: UserProfileUpdate) -> UserProfile:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
