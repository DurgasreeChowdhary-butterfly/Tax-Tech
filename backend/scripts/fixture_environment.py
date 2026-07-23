"""Shared Phase 13 fixture setup — NOT part of the product API surface.

Used by both seed_phase13_data.py (a fresh random user per run, for
Playwright's guided-journey.spec.ts) and seed_demo_user.py (one stable,
documented demo user for manual handoff testing). Kept in one place so the
two scripts can never define two different versions of "what a SUPPORTED
fixture looks like."

Isolated under its own assessment year ("2099-01", obviously not a real AY)
so its questionnaire version and tax_rule_set can never collide with the
real AY 2026-27 fixture backend/scripts/seed_dev_data.py (Phase 12) depends
on — questionnaire_versions/tax_rule_sets are immutable once published, so a
second, incompatible graph/rule set for the same AY is not an option.
"""

from app.models import enums
from app.repositories import filing_session as filing_session_repo
from app.repositories import questionnaire as questionnaire_repo
from app.repositories import tax_rule_set as tax_rule_set_repo
from app.schemas.filing_session import FilingSessionCreate, FilingSessionUpdate
from app.services import consent as consent_service

ASSESSMENT_YEAR = "2099-01"


def ensure_questionnaire_graph(db) -> None:
    if questionnaire_repo.get_published_version_for_assessment_year(db, ASSESSMENT_YEAR) is not None:
        return

    version = questionnaire_repo.create_questionnaire_version(db, assessment_year=ASSESSMENT_YEAR, version_number=1)
    questionnaire_repo.add_question(
        db, version, key="form16_upload", order_index=1,
        question_type=enums.QuestionType.DOCUMENT_UPLOAD, prompt="Upload your Form 16",
    )
    questionnaire_repo.add_question(
        db, version, key="review_extracted_details", order_index=2,
        question_type=enums.QuestionType.REVIEW_CARD, prompt="Review the details we found",
    )
    db.refresh(version)
    questionnaire_repo.publish_questionnaire_version(db, version)


def ensure_tax_rule_set(db) -> None:
    if tax_rule_set_repo.get_published_rule_set_for_assessment_year(db, ASSESSMENT_YEAR) is not None:
        return

    rule_set = tax_rule_set_repo.create_tax_rule_set(db, assessment_year=ASSESSMENT_YEAR, engine_version="phase13-fixture-v1")

    for regime, std_deduction in ((enums.TaxRegime.OLD, "50000.00"), (enums.TaxRegime.NEW, "75000.00")):
        tax_rule_set_repo.add_tax_rule(
            db, rule_set, regime=regime, rule_type=enums.TaxRuleType.DEDUCTION, code="STANDARD_DEDUCTION",
            parameters={"amount": std_deduction},
        )
        tax_rule_set_repo.add_tax_rule(
            db, rule_set, regime=regime, rule_type=enums.TaxRuleType.SLAB, code="SLAB_1",
            parameters={"min": "0.00", "max": "250000.00", "rate": "0.00"}, order_index=1,
        )
        tax_rule_set_repo.add_tax_rule(
            db, rule_set, regime=regime, rule_type=enums.TaxRuleType.SLAB, code="SLAB_2",
            parameters={"min": "250000.00", "max": "1000000000.00", "rate": "0.10"}, order_index=2,
        )
        tax_rule_set_repo.add_tax_rule(
            db, rule_set, regime=regime, rule_type=enums.TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
            parameters={"rate": "0.04"},
        )
        tax_rule_set_repo.add_tax_rule(
            db, rule_set, regime=regime, rule_type=enums.TaxRuleType.REBATE, code="REBATE_87A",
            parameters={"threshold": "500000.00", "max_rebate": "0.00", "marginal_relief": False},
        )

    tax_rule_set_repo.publish_tax_rule_set(db, rule_set)


def ensure_environment(db) -> None:
    """The two idempotent, run-once-per-database steps every fixture user
    needs. Safe to call every time a seed script runs."""
    ensure_questionnaire_graph(db)
    ensure_tax_rule_set(db)


def create_supported_filing_session(db, user):
    """A filing session for `user`, already SUPPORTED-eligible (correct
    filer_category/residency_status/complexity, required consents accepted)
    except for verified income — the caller still has to walk the real
    upload/review UI to produce that, exactly what Phase 13 proves."""
    session = filing_session_repo.create_filing_session(
        db, FilingSessionCreate(user_id=user.id, assessment_year=ASSESSMENT_YEAR)
    )
    session = filing_session_repo.update_filing_session(
        db, session,
        FilingSessionUpdate(
            filer_category=enums.FilerCategory.SALARIED,
            residency_status=enums.ResidencyStatus.RESIDENT,
            complexity=enums.FilingComplexity.SIMPLE,
        ),
    )
    for definition in consent_service.seed_v1_consent_definitions(db):
        consent_service.accept_consent(db, session.id, definition.code)
    return session
