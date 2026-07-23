import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base
from app.models.enums import ActorType, AuditEventCode

JSONType = JSON().with_variant(JSONB(), "postgresql")


class AuditLog(Base):
    """Append-only history of meaningful domain events (docs/DATA_MODEL.md).
    Rows are never updated or deleted — enforced here by never exposing an
    update/delete repository method (app/repositories/audit_log.py), and on
    PostgreSQL by a DB-level trigger rejecting UPDATE/DELETE outright (Phase
    10 migration), mirroring the tax_rule_sets/questionnaire_versions
    immutability-trigger pattern but unconditional (every row, not just
    "published" ones).

    `filing_session_id`/`actor_user_id` use ondelete="SET NULL" rather than
    CASCADE: this table's integrity as a historical record must outlive the
    domain rows it references (even though neither users nor filing_sessions
    are ever deleted by any current code path).

    `metadata_json` is a small, bounded, allowlisted-by-construction JSON
    object — every call site builds it explicitly from safe identifiers
    (codes, versions, counts), never from a raw model object. It must never
    contain PAN, document content, raw extracted values, financial amounts,
    storage keys, provider secrets, or raw exception text (see
    app/audit/service.py's validation).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_filing_session_created", "filing_session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_code: Mapped[AuditEventCode] = mapped_column(
        Enum(AuditEventCode, name="audit_event_code", native_enum=False, create_constraint=True), nullable=False
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", native_enum=False, create_constraint=True), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filing_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("filing_sessions.id", ondelete="SET NULL"), nullable=True
    )
    subject_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    filing_session: Mapped["FilingSession | None"] = relationship()
