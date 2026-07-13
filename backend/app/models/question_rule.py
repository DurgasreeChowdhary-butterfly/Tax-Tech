import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.enums import RuleAction, RuleConditionOperator

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. the SQLite test path).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class QuestionRule(Base):
    """A routing rule: IF <question's answer matches condition> THEN <action>."""

    __tablename__ = "question_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Denormalized from question.questionnaire_version_id — see QuestionOption for why.
    questionnaire_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    condition_operator: Mapped[RuleConditionOperator] = mapped_column(
        Enum(RuleConditionOperator, name="rule_condition_operator", native_enum=False, create_constraint=True),
        nullable=False,
    )
    condition_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    action: Mapped[RuleAction] = mapped_column(
        Enum(RuleAction, name="rule_action", native_enum=False, create_constraint=True), nullable=False
    )
    # Target question for SHOW_QUESTION / SKIP_QUESTION / GO_TO_QUESTION. Null for
    # SET_PROFILE_FLAG / SET_COMPLEXITY / REQUIRE_REVIEW / END_FLOW.
    target_question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=True
    )
    # Inert in Phase 3 — payload for SET_PROFILE_FLAG / SET_COMPLEXITY / REQUIRE_REVIEW,
    # consumed by the Decision Engine (Phase 4).
    action_payload: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question: Mapped["Question"] = relationship(foreign_keys=[question_id])
    target_question: Mapped["Question | None"] = relationship(foreign_keys=[target_question_id])
