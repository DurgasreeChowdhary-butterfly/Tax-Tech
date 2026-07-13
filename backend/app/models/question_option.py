import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class QuestionOption(Base):
    """A selectable option for a SINGLE_CHOICE / MULTI_CHOICE question."""

    __tablename__ = "question_options"
    __table_args__ = (UniqueConstraint("question_id", "value", name="uq_question_options_question_value"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized from question.questionnaire_version_id so the published-version
    # immutability trigger can check this table directly, without a join.
    questionnaire_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="options")
