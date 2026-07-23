import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interest_income import InterestIncome
from app.models.salary_income import SalaryIncome


def list_salary_income_for_session(db: Session, filing_session_id: uuid.UUID) -> list[SalaryIncome]:
    stmt = select(SalaryIncome).where(SalaryIncome.filing_session_id == filing_session_id).order_by(SalaryIncome.id)
    return list(db.execute(stmt).scalars().all())


def list_interest_income_for_session(db: Session, filing_session_id: uuid.UUID) -> list[InterestIncome]:
    stmt = (
        select(InterestIncome).where(InterestIncome.filing_session_id == filing_session_id).order_by(InterestIncome.id)
    )
    return list(db.execute(stmt).scalars().all())


def has_any_verified_income_for_session(db: Session, filing_session_id: uuid.UUID) -> bool:
    """True only if at least one verified salary or interest income record for
    this filing session has an actual confirmed amount — never a placeholder
    row whose fields are all still null. Used by the Supported Case Validator
    to detect INCOMPLETE cases (docs/TAX_ENGINE_BOUNDARY.md).

    Reads only the verified domain tables (salary_income/interest_income) —
    never extracted_fields/document_extractions — preserving the boundary
    that only user-confirmed data may influence a tax engine outcome.
    """
    salary_stmt = (
        select(SalaryIncome.id)
        .where(SalaryIncome.filing_session_id == filing_session_id, SalaryIncome.gross_salary.is_not(None))
        .limit(1)
    )
    if db.execute(salary_stmt).first() is not None:
        return True

    interest_stmt = (
        select(InterestIncome.id)
        .where(InterestIncome.filing_session_id == filing_session_id, InterestIncome.interest_amount.is_not(None))
        .limit(1)
    )
    return db.execute(interest_stmt).first() is not None
