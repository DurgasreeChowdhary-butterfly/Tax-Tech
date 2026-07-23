import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.tax.lifecycle import validate_draft, validate_publishable
from app.models.enums import TaxRegime, TaxRuleSetStatus, TaxRuleType
from app.models.tax_rule import TaxRule
from app.models.tax_rule_set import TaxRuleSet


def create_tax_rule_set(db: Session, *, assessment_year: str, engine_version: str) -> TaxRuleSet:
    rule_set = TaxRuleSet(assessment_year=assessment_year, engine_version=engine_version)
    db.add(rule_set)
    db.commit()
    db.refresh(rule_set)
    return rule_set


def add_tax_rule(
    db: Session,
    rule_set: TaxRuleSet,
    *,
    regime: TaxRegime,
    rule_type: TaxRuleType,
    code: str,
    parameters: dict,
    order_index: int = 0,
) -> TaxRule:
    validate_draft(rule_set)
    rule = TaxRule(
        tax_rule_set_id=rule_set.id,
        regime=regime,
        rule_type=rule_type,
        code=code,
        parameters=parameters,
        order_index=order_index,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def publish_tax_rule_set(db: Session, rule_set: TaxRuleSet) -> TaxRuleSet:
    validate_publishable(rule_set)
    rule_set.status = TaxRuleSetStatus.PUBLISHED
    rule_set.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule_set)
    return rule_set


def get_published_rule_set_for_assessment_year(db: Session, assessment_year: str) -> TaxRuleSet | None:
    stmt = (
        select(TaxRuleSet)
        .where(TaxRuleSet.assessment_year == assessment_year, TaxRuleSet.status == TaxRuleSetStatus.PUBLISHED)
        .order_by(TaxRuleSet.published_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def get_rule_set_by_id(db: Session, rule_set_id: uuid.UUID) -> TaxRuleSet | None:
    return db.get(TaxRuleSet, rule_set_id)


def get_rules_for_rule_set(db: Session, rule_set_id: uuid.UUID) -> list[TaxRule]:
    stmt = select(TaxRule).where(TaxRule.tax_rule_set_id == rule_set_id).order_by(TaxRule.regime, TaxRule.order_index)
    return list(db.execute(stmt).scalars().all())
