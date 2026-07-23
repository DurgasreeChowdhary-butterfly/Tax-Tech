import uuid

from sqlalchemy.orm import Session

from app.engines.tax.supported_case import SupportedCaseInput, SupportedCaseResult, evaluate_supported_case
from app.models.enums import SupportedCaseOutcome
from app.repositories import filing_flag as filing_flag_repo
from app.repositories import income as income_repo
from app.repositories import tax_rule_set as tax_rule_set_repo
from app.services.questionnaire import get_filing_session_or_raise

# Namespaced distinctly from any Decision Engine (Phase 4) flag code so the two
# subsystems' filing_flags rows never collide or clobber each other — see
# app.repositories.filing_flag.reconcile_flags (only touches rows whose code
# is within the `known_flag_codes` set passed to it).
_OUTCOME_FLAG_CODES = {
    SupportedCaseOutcome.NOT_SUPPORTED: "SUPPORTED_CASE_NOT_SUPPORTED",
    SupportedCaseOutcome.REVIEW_REQUIRED: "SUPPORTED_CASE_REVIEW_REQUIRED",
    SupportedCaseOutcome.INCOMPLETE: "SUPPORTED_CASE_INCOMPLETE",
}
_KNOWN_OUTCOME_FLAG_CODES = set(_OUTCOME_FLAG_CODES.values())


def evaluate_filing_session(db: Session, filing_session_id: uuid.UUID) -> SupportedCaseResult:
    """Recomputes the Supported Case Validator outcome from current session
    state and persists it as a filing_flag. Deterministic and idempotent —
    mirrors app.services.decision.reconcile_decision_state: rerunning with an
    unchanged underlying state makes no further writes, and a genuine change
    (e.g. a newly confirmed income record, or a cleared unsupported-scenario
    flag) is always fully reflected.
    """
    filing_session = get_filing_session_or_raise(db, filing_session_id)

    active_flags = frozenset(
        f.flag_code for f in filing_flag_repo.get_all_flags_for_session(db, filing_session_id) if f.is_active
    )
    published_rule_set = tax_rule_set_repo.get_published_rule_set_for_assessment_year(
        db, filing_session.assessment_year
    )
    has_verified_income = income_repo.has_any_verified_income_for_session(db, filing_session_id)

    inputs = SupportedCaseInput(
        filer_category=filing_session.filer_category,
        residency_status=filing_session.residency_status,
        session_complexity=filing_session.complexity,
        active_flag_codes=active_flags,
        has_published_rule_set=published_rule_set is not None,
        has_verified_income=has_verified_income,
    )
    result = evaluate_supported_case(inputs)

    active_outcome_flag_codes = set()
    outcome_flag_code = _OUTCOME_FLAG_CODES.get(result.outcome)
    if outcome_flag_code is not None:
        active_outcome_flag_codes.add(outcome_flag_code)
    filing_flag_repo.reconcile_flags(db, filing_session_id, active_outcome_flag_codes, _KNOWN_OUTCOME_FLAG_CODES)

    return result
