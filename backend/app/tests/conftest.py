import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers all models on Base.metadata)
from app.core.database import Base


@pytest.fixture()
def document_storage(tmp_path):
    from app.integrations.storage.local_filesystem import LocalFilesystemStorage

    return LocalFilesystemStorage(str(tmp_path / "document_storage"))


@pytest.fixture()
def client(db_session, document_storage):
    """Shared TestClient for every API test file (Phase 11 consolidates what
    used to be a near-identical fixture duplicated per file). Wired to the
    test's db_session and an isolated document_storage; carries NO default
    auth — most API test files attach an Authorization header to this same
    client instance from within their own "primary session" fixture (see
    auth_headers() below and e.g. test_document_api.py), so ordinary test
    bodies don't need to touch headers at all. Tests that call `client`
    directly with no session fixture (e.g. an "unknown filing session"
    check) must set headers themselves via auth_headers(user.id).
    """
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.integrations.storage.provider import get_storage_provider
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_storage_provider] = lambda: document_storage
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_headers(user_id) -> dict[str, str]:
    """Not a fixture — a plain helper, importable from any test module, that
    mints a real access token for `user_id` (bypassing the login endpoint,
    since most tests are exercising ownership/authorization, not login
    itself — see test_auth_api.py for login/refresh/logout coverage)."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture()
def uploaded_document(db_session, document_storage):
    """A filing session with one successfully uploaded (real-signature) PDF
    document — shared setup for Phase 6 extraction tests."""
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate
    from app.services import document as document_service

    user = create_user(db_session, UserCreate(email="extraction-fixture@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))

    pdf_bytes = b"%PDF-1.4\n%mock form16 pdf for extraction tests\n"
    tax_document, _is_duplicate = document_service.upload_document(
        db_session, filing_session.id, original_filename="form16.pdf", content=pdf_bytes, storage=document_storage
    )
    return filing_session, tax_document


@pytest.fixture()
def extracted_document(db_session, document_storage, uploaded_document):
    """An uploaded document that has already been through a successful
    extraction — shared setup for Phase 7 verification tests. Returns
    (filing_session, tax_document, extraction, fields_by_name)."""
    from app.repositories import document_processing as document_processing_repo
    from app.services import extraction as extraction_service

    filing_session, tax_document = uploaded_document
    job = extraction_service.start_extraction(db_session, filing_session.id, tax_document.id, storage=document_storage)
    extraction = document_processing_repo.get_extraction_for_job(db_session, job.id)
    fields = document_processing_repo.list_fields_for_extraction(db_session, extraction.id)
    fields_by_name = {f.field_name: f for f in fields}
    return filing_session, tax_document, extraction, fields_by_name


@pytest.fixture()
def published_tax_rule_set(db_session):
    """A published tax_rule_set for AY 2026-27 covering both regimes with a
    minimal, structurally-representative set of rules (slab/rebate/cess/
    deduction). Illustrative content for Phase 8 (Supported Case Validator +
    versioning/immutability) tests only — Phase 9's golden-fixture tests are
    the authority on exact calculation-accurate figures.
    """
    from app.models.enums import TaxRegime, TaxRuleType
    from app.repositories import tax_rule_set as tax_rule_set_repo

    rule_set = tax_rule_set_repo.create_tax_rule_set(db_session, assessment_year="2026-27", engine_version="v1")

    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.DEDUCTION, code="STANDARD_DEDUCTION",
        parameters={"amount": "50000.00"},
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.SLAB, code="SLAB_1",
        parameters={"min": "0.00", "max": "250000.00", "rate": "0.00"}, order_index=1,
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.SLAB, code="SLAB_2",
        parameters={"min": "250000.00", "max": "500000.00", "rate": "0.05"}, order_index=2,
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.OLD, rule_type=TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
        parameters={"rate": "0.04"},
    )

    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.DEDUCTION, code="STANDARD_DEDUCTION",
        parameters={"amount": "75000.00"},
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.SLAB, code="SLAB_1",
        parameters={"min": "0.00", "max": "400000.00", "rate": "0.00"}, order_index=1,
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.SLAB, code="SLAB_2",
        parameters={"min": "400000.00", "max": "800000.00", "rate": "0.05"}, order_index=2,
    )
    tax_rule_set_repo.add_tax_rule(
        db_session, rule_set, regime=TaxRegime.NEW, rule_type=TaxRuleType.CESS, code="HEALTH_EDUCATION_CESS",
        parameters={"rate": "0.04"},
    )

    return tax_rule_set_repo.publish_tax_rule_set(db_session, rule_set)


@pytest.fixture()
def real_fy2025_26_rule_set(db_session):
    """The actual, officially-sourced FY 2025-26/AY 2026-27 V1 rule set (see
    app/engines/tax/rule_data.py for full source citations) — the authority
    for Phase 9 golden-fixture/calculation-accuracy tests, as opposed to
    `published_tax_rule_set`'s illustrative Phase 8 placeholder content."""
    from app.engines.tax.rule_data import seed_fy_2025_26_v1_rule_set

    return seed_fy_2025_26_v1_rule_set(db_session)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def questionnaire_fixture(db_session):
    """Builds and publishes a small, deterministic 5-question graph.

    Q1 has_other_income (BOOLEAN)   -> if false, SKIP Q2
    Q2 other_income_count (NUMBER)
    Q3 filing_intent (SINGLE_CHOICE: GUIDED/QUICK) -> if QUICK, GOTO Q5 (and SKIP Q4 as a fallback)
    Q4 extra_details (TEXT, optional)
    Q5 confirm_ready (BOOLEAN)

    Returns (version, questions) where `questions` maps key -> Question.
    """
    from app.models.enums import QuestionType, RuleAction, RuleConditionOperator
    from app.repositories import questionnaire as repo

    version = repo.create_questionnaire_version(db_session, assessment_year="2026-27", version_number=1)

    q1 = repo.add_question(
        db_session, version, key="has_other_income", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="Do you have any other income sources?",
    )
    q2 = repo.add_question(
        db_session, version, key="other_income_count", order_index=2,
        question_type=QuestionType.NUMBER, prompt="How many other income sources?",
    )
    q3 = repo.add_question(
        db_session, version, key="filing_intent", order_index=3,
        question_type=QuestionType.SINGLE_CHOICE, prompt="How would you like to proceed?",
    )
    repo.add_question_option(db_session, q3, value="GUIDED", label="Guided walkthrough", order_index=1)
    repo.add_question_option(db_session, q3, value="QUICK", label="Quick estimate", order_index=2)
    q4 = repo.add_question(
        db_session, version, key="extra_details", order_index=4,
        question_type=QuestionType.TEXT, prompt="Anything else you'd like to add?", is_required=False,
    )
    q5 = repo.add_question(
        db_session, version, key="confirm_ready", order_index=5,
        question_type=QuestionType.BOOLEAN, prompt="Ready to see your summary?",
    )

    repo.add_question_rule(
        db_session, q1, action=RuleAction.SKIP_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=False, target_question=q2, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.GO_TO_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q5, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.SKIP_QUESTION, condition_operator=RuleConditionOperator.EQUALS,
        condition_value="QUICK", target_question=q4, priority=10,
    )

    db_session.refresh(version)
    repo.publish_questionnaire_version(db_session, version)

    questions = {"has_other_income": q1, "other_income_count": q2, "filing_intent": q3, "extra_details": q4, "confirm_ready": q5}
    return version, questions


@pytest.fixture()
def consent_definitions_v1(db_session):
    """Publishes the V1 required consent definitions (DATA_PROCESSING,
    DOCUMENT_STORAGE_AND_PROCESSING) — shared setup for Phase 10 consent/audit
    tests. See app/services/consent.py::seed_v1_consent_definitions."""
    from app.services import consent as consent_service

    return consent_service.seed_v1_consent_definitions(db_session)


@pytest.fixture()
def consented_filing_session(db_session, consent_definitions_v1):
    """A filing session whose owning user has already accepted every V1
    required consent — shared setup for Phase 10 tests (document upload,
    extraction, etc.) that exercise flows downstream of the consent gate
    without re-testing the gate itself each time."""
    from app.repositories.filing_session import create_filing_session
    from app.repositories.user import create_user
    from app.schemas.filing_session import FilingSessionCreate
    from app.schemas.user import UserCreate
    from app.services import consent as consent_service

    user = create_user(db_session, UserCreate(email="consented@example.com", password="TestPassword123!"))
    filing_session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    for definition in consent_definitions_v1:
        consent_service.accept_consent(db_session, filing_session.id, definition.code)
    return filing_session


@pytest.fixture()
def decision_fixture(db_session):
    """Builds and publishes a small graph exercising all Phase 4 decision actions.

    Q1 has_freelance_income (BOOLEAN) -> true: SET_PROFILE_FLAG(FREELANCE_INCOME_DETECTED)
                                          true: SET_COMPLEXITY(REVIEW_REQUIRED)
    Q2 has_crypto_income (BOOLEAN)    -> true: SET_COMPLEXITY(REVIEW_REQUIRED)  [shared support with Q1 for complexity]
                                          true: REQUIRE_REVIEW
    Q3 has_other_review_trigger (BOOLEAN) -> true: REQUIRE_REVIEW  [shared support with Q2 for REVIEW_REQUIRED flag]
    Q4 confirm_end (BOOLEAN)         -> true: END_FLOW

    Returns (version, questions) where `questions` maps key -> Question.
    """
    from app.models.enums import FilingComplexity, QuestionType, RuleAction, RuleConditionOperator
    from app.repositories import questionnaire as repo

    version = repo.create_questionnaire_version(db_session, assessment_year="2026-27", version_number=1)

    q1 = repo.add_question(
        db_session, version, key="has_freelance_income", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="Do you have freelance income?",
    )
    q2 = repo.add_question(
        db_session, version, key="has_crypto_income", order_index=2,
        question_type=QuestionType.BOOLEAN, prompt="Do you have crypto income?",
    )
    q3 = repo.add_question(
        db_session, version, key="has_other_review_trigger", order_index=3,
        question_type=QuestionType.BOOLEAN, prompt="Any other reason you think you need review?",
    )
    q4 = repo.add_question(
        db_session, version, key="confirm_end", order_index=4,
        question_type=QuestionType.BOOLEAN, prompt="Stop here?",
    )

    repo.add_question_rule(
        db_session, q1, action=RuleAction.SET_PROFILE_FLAG, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"flag": "FREELANCE_INCOME_DETECTED"}, priority=0,
    )
    repo.add_question_rule(
        db_session, q1, action=RuleAction.SET_COMPLEXITY, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"complexity": FilingComplexity.REVIEW_REQUIRED.value}, priority=0,
    )
    repo.add_question_rule(
        db_session, q2, action=RuleAction.SET_COMPLEXITY, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"complexity": FilingComplexity.REVIEW_REQUIRED.value}, priority=0,
    )
    repo.add_question_rule(
        db_session, q2, action=RuleAction.REQUIRE_REVIEW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )
    repo.add_question_rule(
        db_session, q3, action=RuleAction.REQUIRE_REVIEW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )
    repo.add_question_rule(
        db_session, q4, action=RuleAction.END_FLOW, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, priority=0,
    )

    db_session.refresh(version)
    repo.publish_questionnaire_version(db_session, version)

    questions = {
        "has_freelance_income": q1,
        "has_crypto_income": q2,
        "has_other_review_trigger": q3,
        "confirm_end": q4,
    }
    return version, questions
