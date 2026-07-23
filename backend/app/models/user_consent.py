import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import UserConsentStatus


class UserConsent(Base):
    """Per-user acceptance/withdrawal history for one consent_definitions
    version, scoped to the filing session it was given for (Phase 10 wires
    consent only into filing-session-scoped flows — e.g. document upload —
    so `filing_session_id` is required for every row this codebase writes;
    left nullable at the schema level only so a future user-level-only
    consent type doesn't require a migration, per docs/DATA_MODEL.md's
    "where applicable").

    Append-only, mirroring QuestionAnswer/ExtractedFieldVerification exactly:
    every accept/withdraw action is a NEW row (never an in-place update), so
    "never silently overwrite previous consent history" holds structurally,
    not just by convention. `is_current` + the partial unique index below
    mark the single most recent row per (user, filing_session,
    consent_definition) — re-acceptance after withdrawal always creates a
    fresh row, never resurrects the old one.
    """

    __tablename__ = "user_consents"
    __table_args__ = (
        Index(
            "uq_user_consents_current",
            "user_id",
            "filing_session_id",
            "consent_definition_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filing_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=True
    )
    consent_definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("consent_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[UserConsentStatus] = mapped_column(
        Enum(UserConsentStatus, name="user_consent_status", native_enum=False, create_constraint=True), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_consents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    consent_definition: Mapped["ConsentDefinition"] = relationship(back_populates="user_consents")
