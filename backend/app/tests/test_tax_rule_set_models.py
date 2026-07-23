import pytest
from sqlalchemy.exc import IntegrityError

from app.engines.tax.errors import EmptyTaxRuleSetError, PublishedRuleSetImmutableError
from app.models.enums import TaxRegime, TaxRuleSetStatus, TaxRuleType
from app.repositories import tax_rule_set as tax_rule_set_repo


def test_publishing_rule_set_requires_at_least_one_rule(db_session):
    rule_set = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2026-27", engine_version="v1")

    with pytest.raises(EmptyTaxRuleSetError):
        tax_rule_set_repo.publish_tax_rule_set(db_session, rule_set)


def test_published_rule_set_rejects_new_rules(db_session, published_tax_rule_set):
    with pytest.raises(PublishedRuleSetImmutableError):
        tax_rule_set_repo.add_tax_rule(
            db_session, published_tax_rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.DEDUCTION,
            code="LATE_ADDITION", parameters={"amount": "1.00"},
        )


def test_published_rule_set_rejects_republish(db_session, published_tax_rule_set):
    with pytest.raises(PublishedRuleSetImmutableError):
        tax_rule_set_repo.publish_tax_rule_set(db_session, published_tax_rule_set)


def test_rule_set_relationships(published_tax_rule_set):
    assert published_tax_rule_set.status == TaxRuleSetStatus.PUBLISHED
    assert published_tax_rule_set.published_at is not None
    assert len(published_tax_rule_set.tax_rules) == 8
    regimes = {r.regime for r in published_tax_rule_set.tax_rules}
    assert regimes == {TaxRegime.OLD, TaxRegime.NEW}


def test_unique_constraint_assessment_year_engine_version(db_session, published_tax_rule_set):
    tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2026-27", engine_version="v2")  # distinct, OK

    from app.models.tax_rule_set import TaxRuleSet

    db_session.add(TaxRuleSet(assessment_year="2026-27", engine_version="v1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_constraint_rule_set_regime_code(db_session):
    rule_set = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2027-28", engine_version="v1")
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
        parameters={"rate": "0.04"},
    )

    with pytest.raises(IntegrityError):
        tax_rule_set_repo.add_tax_rule(
            db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
            parameters={"rate": "0.05"},
        )
    db_session.rollback()


def test_deleting_rule_set_cascades_to_rules(db_session):
    from app.models.tax_rule import TaxRule

    rule_set = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2028-29", engine_version="v1")
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
        parameters={"rate": "0.04"},
    )

    db_session.delete(rule_set)
    db_session.commit()

    assert db_session.query(TaxRule).filter_by(tax_rule_set_id=rule_set.id).count() == 0


def test_get_published_rule_set_for_assessment_year(db_session, published_tax_rule_set):
    found = tax_rule_set_repo.get_published_rule_set_for_assessment_year(db_session, "2026-27")
    assert found is not None
    assert found.id == published_tax_rule_set.id

    assert tax_rule_set_repo.get_published_rule_set_for_assessment_year(db_session, "2099-00") is None
