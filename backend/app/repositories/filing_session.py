import uuid

from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.models.enums import ActorType, AuditEventCode
from app.models.filing_session import FilingSession
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate


def create_filing_session(db: Session, data: FilingSessionCreate) -> FilingSession:
    session = FilingSession(user_id=data.user_id, assessment_year=data.assessment_year)
    db.add(session)
    db.flush()

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.FILING_SESSION_CREATED,
        actor_type=ActorType.USER,
        actor_user_id=data.user_id,
        filing_session_id=session.id,
        subject_type="filing_session",
        subject_id=session.id,
        metadata={"assessment_year": data.assessment_year},
    )

    db.commit()
    db.refresh(session)
    return session


def get_filing_session(db: Session, session_id: uuid.UUID) -> FilingSession | None:
    return db.get(FilingSession, session_id)


def update_filing_session(db: Session, session: FilingSession, data: FilingSessionUpdate) -> FilingSession:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session
