import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.enums import QuestionnaireVersionStatus


class QuestionnaireVersion(Base):
    """A published, immutable snapshot of a question graph for one assessment year.

    Immutability of PUBLISHED rows (and their questions/options/rules) is also
    enforced at the database level via triggers added in the Phase 3 migration —
    see alembic/versions for `fn_reject_change_to_published_questionnaire_version`.
    """

    __tablename__ = "questionnaire_versions"
    __table_args__ = (UniqueConstraint("assessment_year", "version_number", name="uq_questionnaire_version_ay_num"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_year: Mapped[str] = mapped_column(String(9), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QuestionnaireVersionStatus] = mapped_column(
        Enum(QuestionnaireVersionStatus, name="questionnaire_version_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=QuestionnaireVersionStatus.DRAFT,
        server_default=QuestionnaireVersionStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    questions: Mapped[list["Question"]] = relationship(back_populates="questionnaire_version", cascade="all, delete-orphan")
