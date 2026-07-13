import uuid

from sqlalchemy.orm import Session

from app.models.tax_profile import TaxProfile
from app.schemas.tax_profile import TaxProfileCreate, TaxProfileUpdate


def create_tax_profile(db: Session, data: TaxProfileCreate) -> TaxProfile:
    profile = TaxProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_tax_profile(db: Session, profile_id: uuid.UUID) -> TaxProfile | None:
    return db.get(TaxProfile, profile_id)


def update_tax_profile(db: Session, profile: TaxProfile, data: TaxProfileUpdate) -> TaxProfile:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
