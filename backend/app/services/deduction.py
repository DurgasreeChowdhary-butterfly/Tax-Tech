import uuid

from sqlalchemy.orm import Session

from app.engines.tax.deductions import validate_deduction_claim
from app.models.deduction import Deduction
from app.repositories import deduction as deduction_repo
from app.services.questionnaire import get_filing_session_or_raise


def claim_deduction(db: Session, filing_session_id: uuid.UUID, code: str, claimed_amount: object) -> Deduction:
    """Validates the deduction code against the closed V1 vocabulary and the
    claimed amount's shape (Decimal string, non-negative, <=2 decimals)
    before ever writing anything — an unsupported code or invalid value never
    reaches the deductions table (mirrors app.engines.extraction.field_mapping's
    validate-before-write ordering)."""
    filing_session = get_filing_session_or_raise(db, filing_session_id)
    validated_amount = validate_deduction_claim(code, claimed_amount)
    return deduction_repo.upsert_deduction_claim(
        db, filing_session_id, code, validated_amount, actor_user_id=filing_session.user_id
    )
