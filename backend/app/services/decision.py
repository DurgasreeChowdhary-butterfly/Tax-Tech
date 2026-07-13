import uuid

from sqlalchemy.orm import Session

from app.engines.decision.resolver import DecisionState, compute_decision_state
from app.models.enums import FilingComplexity
from app.repositories import filing_flag as filing_flag_repo
from app.services.questionnaire import ensure_bound_version, get_filing_session_or_raise, load_routing_inputs


def reconcile_decision_state(db: Session, filing_session_id: uuid.UUID) -> DecisionState:
    """Recompute effective decision state from current answers and persist it.

    Deterministic and idempotent: rerunning with an unchanged answer set makes
    no further writes. Only ever touches filing_flags rows whose flag_code is
    emittable by a rule in this session's bound questionnaire version — no
    other workflow state (status, unrelated flags) is touched.
    """
    filing_session = get_filing_session_or_raise(db, filing_session_id)
    version = ensure_bound_version(db, filing_session)
    questions, rules_by_question_id, answers_by_question_id = load_routing_inputs(db, filing_session, version)

    state = compute_decision_state(questions, rules_by_question_id, answers_by_question_id)

    filing_flag_repo.reconcile_flags(db, filing_session_id, state.active_flags, state.known_flags)

    target_complexity = FilingComplexity(state.complexity) if state.complexity else FilingComplexity.UNDETERMINED
    if filing_session.complexity != target_complexity:
        filing_session.complexity = target_complexity
        db.commit()
        db.refresh(filing_session)

    return state


def get_decision_state(db: Session, filing_session_id: uuid.UUID) -> tuple[FilingComplexity, list]:
    """Read-only: the currently persisted decision state (kept fresh by
    `reconcile_decision_state`, which runs on every answer submission)."""
    filing_session = get_filing_session_or_raise(db, filing_session_id)
    flags = filing_flag_repo.get_all_flags_for_session(db, filing_session_id)
    return filing_session.complexity, flags
