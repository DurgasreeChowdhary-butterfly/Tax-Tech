import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import ActorType, AuditEventCode
from app.repositories import audit_log as audit_log_repo

_MAX_METADATA_KEYS = 8
_MAX_STRING_VALUE_LENGTH = 200
_ALLOWED_METADATA_VALUE_TYPES = (str, int, float, bool)

# Key-name substrings that must never appear in audit metadata, regardless of
# value type/length — a second, independent layer of data minimization on top
# of the type/length bound above. Every legitimate metadata key used by this
# codebase's call sites (e.g. "flag_code", "field_name", "regime",
# "tax_rule_set_id", "content_type") is a safe identifier and matches none of
# these ("content_type" names a MIME type like "application/pdf", not
# document content, so "content" itself is deliberately not in this list).
_FORBIDDEN_METADATA_KEY_SUBSTRINGS = (
    "pan",
    "amount",
    "value",
    "token",
    "password",
    "secret",
    "storage_key",
    "exception",
)


class UnsafeAuditMetadataError(ValueError):
    """Raised when a caller tries to stage metadata that isn't a small,
    bounded, primitive-valued dict — the structural guard behind Phase 10's
    data-minimization requirement (docs: never PAN, amounts, storage keys,
    raw exception text, etc. in audit metadata). Every call site in this
    codebase builds metadata explicitly from safe identifiers, so this should
    never fire in practice; it exists to fail loudly if one ever doesn't."""


def _validate_metadata(metadata: dict | None) -> None:
    if metadata is None:
        return
    if len(metadata) > _MAX_METADATA_KEYS:
        raise UnsafeAuditMetadataError(f"audit metadata has {len(metadata)} keys, max {_MAX_METADATA_KEYS}")
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise UnsafeAuditMetadataError(f"audit metadata key {key!r} is not a string")
        lowered_key = key.lower()
        for forbidden in _FORBIDDEN_METADATA_KEY_SUBSTRINGS:
            if forbidden in lowered_key:
                raise UnsafeAuditMetadataError(f"audit metadata key {key!r} looks unsafe (matches {forbidden!r})")
        if value is None:
            continue
        if not isinstance(value, _ALLOWED_METADATA_VALUE_TYPES):
            raise UnsafeAuditMetadataError(f"audit metadata key {key!r} has unsafe value type {type(value)!r}")
        if isinstance(value, str) and len(value) > _MAX_STRING_VALUE_LENGTH:
            raise UnsafeAuditMetadataError(f"audit metadata key {key!r} string value exceeds {_MAX_STRING_VALUE_LENGTH} chars")


def stage_event(
    db: Session,
    *,
    event_code: AuditEventCode,
    actor_type: ActorType,
    actor_user_id: uuid.UUID | None = None,
    filing_session_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Stages one audit event in the CURRENT transaction — adds and flushes,
    never commits. Call this immediately before the `db.commit()` that
    persists the domain write it documents, so a rollback of that commit
    rolls back this event too (Phase 10 transactional-consistency
    requirement: a successful domain change and its audit event must never
    diverge). Never call this before a domain operation that might still
    fail — only once the write is known to be happening.
    """
    if actor_type == ActorType.USER and actor_user_id is None:
        raise ValueError("actor_user_id is required when actor_type is USER")
    _validate_metadata(metadata)

    return audit_log_repo.add_event(
        db,
        event_code=event_code,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type=subject_type,
        subject_id=subject_id,
        metadata=metadata,
    )
