import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.engines.tax.calculation import CalculationResult
from app.models.calculation_line_item import CalculationLineItem
from app.models.enums import ActorType, AuditEventCode, TaxRegime
from app.models.tax_calculation import TaxCalculation


def get_current_calculation(db: Session, filing_session_id: uuid.UUID, regime: TaxRegime) -> TaxCalculation | None:
    stmt = select(TaxCalculation).where(
        TaxCalculation.filing_session_id == filing_session_id,
        TaxCalculation.regime == regime,
        TaxCalculation.is_current.is_(True),
    )
    return db.execute(stmt).scalars().first()


def get_calculation_history(db: Session, filing_session_id: uuid.UUID, regime: TaxRegime) -> list[TaxCalculation]:
    stmt = (
        select(TaxCalculation)
        .where(TaxCalculation.filing_session_id == filing_session_id, TaxCalculation.regime == regime)
        .order_by(TaxCalculation.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def get_line_items(db: Session, tax_calculation_id: uuid.UUID) -> list[CalculationLineItem]:
    stmt = (
        select(CalculationLineItem)
        .where(CalculationLineItem.tax_calculation_id == tax_calculation_id)
        .order_by(CalculationLineItem.sequence_index)
    )
    return list(db.execute(stmt).scalars().all())


def record_calculation(
    db: Session,
    *,
    filing_session_id: uuid.UUID,
    tax_rule_set_id: uuid.UUID,
    regime: TaxRegime,
    calculation_engine_version: str,
    input_fingerprint: str,
    result: CalculationResult,
    actor_user_id: uuid.UUID,
) -> TaxCalculation:
    """Idempotent: an exact retry (same fingerprint + same rule set + same
    engine version as the current row) returns the existing row unchanged —
    no new version, no new audit event. Any genuine change creates a new row
    that supersedes the old one, which is flipped non-current in the same
    transaction — mirrors the ExtractedFieldVerification/QuestionAnswer
    append-only-history idiom, and stages TAX_CALCULATION_CREATED (no prior
    current calculation) or TAX_CALCULATION_RECALCULATED (one existed) in
    that same transaction. Audit metadata is limited to the regime, rule set
    id, and engine version — never any of the computed monetary figures.
    """
    current = get_current_calculation(db, filing_session_id, regime)
    if (
        current is not None
        and current.input_fingerprint == input_fingerprint
        and current.tax_rule_set_id == tax_rule_set_id
        and current.calculation_engine_version == calculation_engine_version
    ):
        return current

    new_calc = TaxCalculation(
        filing_session_id=filing_session_id,
        tax_rule_set_id=tax_rule_set_id,
        regime=regime,
        calculation_engine_version=calculation_engine_version,
        input_fingerprint=input_fingerprint,
        is_current=True,
        supersedes_id=current.id if current else None,
        gross_total_income=result.gross_total_income,
        total_deductions_applied=result.total_deductions_applied,
        taxable_income=result.taxable_income,
        tax_before_rebate=result.tax_before_rebate,
        rebate_amount=result.rebate_amount,
        tax_after_rebate=result.tax_after_rebate,
        cess_amount=result.cess_amount,
        total_tax_liability=result.total_tax_liability,
        total_tds_credit=result.total_tds_credit,
        net_payable=result.net_payable,
    )
    if current is not None:
        current.is_current = False
    db.add(new_calc)
    db.flush()  # assign new_calc.id before creating dependent line item rows

    for item in result.line_items:
        db.add(
            CalculationLineItem(
                tax_calculation_id=new_calc.id,
                step_code=item.step_code,
                sequence_index=item.sequence_index,
                amount=item.amount,
                step_metadata=item.metadata or None,
            )
        )

    audit_service.stage_event(
        db,
        event_code=AuditEventCode.TAX_CALCULATION_RECALCULATED if current is not None else AuditEventCode.TAX_CALCULATION_CREATED,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        filing_session_id=filing_session_id,
        subject_type="tax_calculation",
        subject_id=new_calc.id,
        metadata={
            "regime": regime.value,
            "tax_rule_set_id": str(tax_rule_set_id),
            "calculation_engine_version": calculation_engine_version,
        },
    )

    db.commit()
    db.refresh(new_calc)
    return new_calc
