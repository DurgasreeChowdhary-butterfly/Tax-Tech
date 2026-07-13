import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class QuestionAnswer(Base):
    """Immutable, append-only answer history. Rows are never updated in place.

    Re-answering creates a new row (pointing back to what it supersedes) and
    flips the previous row's `is_current` to false in the same transaction.
    Exactly one row may be current per (filing_session, question) — enforced by
    the partial unique index below, not just application logic.
    """

    __tablename__ = "question_answers"
    __table_args__ = (
        Index(
            "uq_question_answers_current",
            "filing_session_id",
            "question_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filing_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    questionnaire_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question_answers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question: Mapped["Question"] = relationship()
