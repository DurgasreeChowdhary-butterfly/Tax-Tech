import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.engines.tax import calculation as calculation_engine
from app.engines.tax.calculation import CALCULATION_ENGINE_VERSION
from app.engines.tax.errors import CaseNotSupportedForCalculationError, NoPublishedRuleSetError
from app.models.calculation_line_item import CalculationLineItem
from app.models.enums import SupportedCaseOutcome, TaxRegime
from app.models.tax_calculation import TaxCalculation
from app.repositories import deduction as deduction_repo
from app.repositories import income as income_repo
from app.repositories import tax_calculation as tax_calculation_repo
from app.repositories import tax_rule_set as tax_rule_set_repo
from app.services import supported_case as supported_case_service
from app.services.questionnaire import get_filing_session_or_raise


def _build_input_fingerprint(
    *, tax_rule_set_id: uuid.UUID, regime: TaxRegime, calculation_engine_version: str, salary_rows, interest_rows, deduction_rows
) -> str:
    """SHA-256 hex digest of a canonical, verified-inputs-only payload. Used
    only to detect exact-retry idempotency — never reversible to the
    underlying amounts, and contains no PAN, document content, or storage
    keys (only internal row UUIDs, Decimal-as-string amounts, the rule set
    id, regime, and engine version)."""
    salary_entries = [
        (
            str(row.id),
            str(row.gross_salary) if row.gross_salary is not None else None,
            str(row.tds_deducted) if row.tds_deducted is not None else None,
        )
        for row in salary_rows
    ]
    salary_entries.sort(key=lambda t: t[0])

    interest_entries = [
        (str(row.id), str(row.interest_amount) if row.interest_amount is not None else None) for row in interest_rows
    ]
    interest_entries.sort(key=lambda t: t[0])

    deduction_entries = [(row.code, str(row.claimed_amount)) for row in deduction_rows]
    deduction_entries.sort(key=lambda t: t[0])

    canonical = {
        "tax_rule_set_id": str(tax_rule_set_id),
        "regime": regime.value,
        "engine_version": calculation_engine_version,
        "salary": salary_entries,
        "interest": interest_entries,
        "deductions": deduction_entries,
    }
    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def calculate_tax(
    db: Session, filing_session_id: uuid.UUID, regime: TaxRegime
) -> tuple[TaxCalculation, list[CalculationLineItem]]:
    """The Phase 9 calculation pipeline entry point (docs/TAX_ENGINE_BOUNDARY.md).
    Recompute-not-accumulate: always reloads current verified inputs and
    recomputes from scratch; persistence (app.repositories.tax_calculation)
    is what makes an unchanged recompute a no-op (idempotent) and a genuine
    change a new version. Only verified domain records (salary_income,
    interest_income, deductions) and the exact published tax_rule_set are
    ever read here — never extracted_fields/document_extractions/OCR output.
    """
    filing_session = get_filing_session_or_raise(db, filing_session_id)

    supported_result = supported_case_service.evaluate_filing_session(db, filing_session_id)
    if supported_result.outcome != SupportedCaseOutcome.SUPPORTED:
        raise CaseNotSupportedForCalculationError(supported_result.outcome.value)

    rule_set = tax_rule_set_repo.get_published_rule_set_for_assessment_year(db, filing_session.assessment_year)
    if rule_set is None:
        raise NoPublishedRuleSetError(filing_session.assessment_year)

    all_rules = tax_rule_set_repo.get_rules_for_rule_set(db, rule_set.id)
    rules_for_regime = [r for r in all_rules if r.regime == regime]

    salary_rows = income_repo.list_salary_income_for_session(db, filing_session_id)
    interest_rows = income_repo.list_interest_income_for_session(db, filing_session_id)
    deduction_rows = deduction_repo.list_deduction_claims_for_session(db, filing_session_id)

    total_gross_salary = sum((row.gross_salary for row in salary_rows if row.gross_salary is not None), Decimal("0.00"))
    total_tds_deducted = sum((row.tds_deducted for row in salary_rows if row.tds_deducted is not None), Decimal("0.00"))
    total_interest_income = sum(
        (row.interest_amount for row in interest_rows if row.interest_amount is not None), Decimal("0.00")
    )
    deduction_claims = {row.code: row.claimed_amount for row in deduction_rows}

    result = calculation_engine.calculate(
        rules=rules_for_regime,
        total_gross_salary=total_gross_salary,
        total_tds_deducted=total_tds_deducted,
        total_interest_income=total_interest_income,
        deduction_claims=deduction_claims,
    )

    fingerprint = _build_input_fingerprint(
        tax_rule_set_id=rule_set.id,
        regime=regime,
        calculation_engine_version=CALCULATION_ENGINE_VERSION,
        salary_rows=salary_rows,
        interest_rows=interest_rows,
        deduction_rows=deduction_rows,
    )

    tax_calculation = tax_calculation_repo.record_calculation(
        db,
        filing_session_id=filing_session_id,
        tax_rule_set_id=rule_set.id,
        regime=regime,
        calculation_engine_version=CALCULATION_ENGINE_VERSION,
        input_fingerprint=fingerprint,
        result=result,
        actor_user_id=filing_session.user_id,
    )
    line_items = tax_calculation_repo.get_line_items(db, tax_calculation.id)
    return tax_calculation, line_items
