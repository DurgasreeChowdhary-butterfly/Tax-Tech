import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class User(Base):
    """Auth identity anchor. `hashed_password` is a bcrypt hash (see
    app/core/security.py) — the raw password is never stored, logged, or
    returned by any API schema."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    tax_profile: Mapped["TaxProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    filing_sessions: Mapped[list["FilingSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
