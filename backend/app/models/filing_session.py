import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import FilerCategory, FilingComplexity, FilingSessionStatus, ResidencyStatus


class FilingSession(Base):
    """One per user per assessment year attempt. The resumable workflow unit."""

    __tablename__ = "filing_sessions"
    __table_args__ = (UniqueConstraint("user_id", "assessment_year", name="uq_filing_sessions_user_ay"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assessment_year: Mapped[str] = mapped_column(String(9), nullable=False)
    status: Mapped[FilingSessionStatus] = mapped_column(
        Enum(FilingSessionStatus, name="filing_session_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=FilingSessionStatus.IN_PROGRESS,
        server_default=FilingSessionStatus.IN_PROGRESS.value,
    )
    complexity: Mapped[FilingComplexity] = mapped_column(
        Enum(FilingComplexity, name="filing_complexity", native_enum=False, create_constraint=True),
        nullable=False,
        default=FilingComplexity.UNDETERMINED,
        server_default=FilingComplexity.UNDETERMINED.value,
    )
    # Assessment-year-specific tax context (can legitimately differ year to
    # year), as distinct from the stable taxpayer identity in TaxProfile.
    residency_status: Mapped[ResidencyStatus | None] = mapped_column(
        Enum(ResidencyStatus, name="residency_status", native_enum=False, create_constraint=True), nullable=True
    )
    filer_category: Mapped[FilerCategory | None] = mapped_column(
        Enum(FilerCategory, name="filer_category", native_enum=False, create_constraint=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="filing_sessions")
