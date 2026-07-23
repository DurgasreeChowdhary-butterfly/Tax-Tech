from app.models.enums import FilingComplexity
from app.repositories import filing_flag as filing_flag_repo
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate
from app.services import questionnaire as questionnaire_service


def _make_session(db_session, email):
    user = create_user(db_session, UserCreate(email=email, password="TestPassword123!"))
    return create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))


def _active_codes(db_session, session_id) -> set[str]:
    return {f.flag_code for f in filing_flag_repo.get_all_flags_for_session(db_session, session_id) if f.is_active}


def test_profile_flag_created_from_answer(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "flagcreate@example.com")

    questionnaire_service.submit_answer(db_session, session.id, questions["has_freelance_income"].id, True)

    assert "FREELANCE_INCOME_DETECTED" in _active_codes(db_session, session.id)


def test_complexity_changes_from_rule_action(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "complexity@example.com")

    assert session.complexity == FilingComplexity.UNDETERMINED

    questionnaire_service.submit_answer(db_session, session.id, questions["has_freelance_income"].id, True)

    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED


def test_review_required_behaviour(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "review@example.com")

    questionnaire_service.submit_answer(db_session, session.id, questions["has_crypto_income"].id, True)

    assert "REVIEW_REQUIRED" in _active_codes(db_session, session.id)


def test_review_required_is_unambiguous_via_complexity_alone(db_session, decision_fixture):
    """Regression: has_other_review_trigger has ONLY a REQUIRE_REVIEW rule, no
    SET_COMPLEXITY rule. A gate that checks only filing_session.complexity
    (not filing_flags) must still be able to see that review is required."""
    _version, questions = decision_fixture
    session = _make_session(db_session, "unambiguous-review@example.com")

    questionnaire_service.submit_answer(db_session, session.id, questions["has_other_review_trigger"].id, True)

    assert "REVIEW_REQUIRED" in _active_codes(db_session, session.id)
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED  # not UNDETERMINED

    # Removing that sole support reverts complexity too — no stale severity left behind.
    questionnaire_service.submit_answer(db_session, session.id, questions["has_other_review_trigger"].id, False)
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.UNDETERMINED
    assert "REVIEW_REQUIRED" not in _active_codes(db_session, session.id)


def test_repeated_reactivation_keeps_single_row_with_correct_current_state(db_session, decision_fixture):
    """inactive -> active -> inactive -> active: the flag row's current state
    must be correct after each transition, and no duplicate rows are ever
    created (the effective-state table is not a transition log — see
    FilingFlag's docstring — but its CURRENT state must always be right)."""
    _version, questions = decision_fixture
    session = _make_session(db_session, "reactivation@example.com")
    q1 = questions["has_freelance_income"]

    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)  # -> active
    questionnaire_service.submit_answer(db_session, session.id, q1.id, False)  # -> inactive
    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)  # -> active again
    questionnaire_service.submit_answer(db_session, session.id, q1.id, False)  # -> inactive again
    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)  # -> active a third time

    all_rows = filing_flag_repo.get_all_flags_for_session(db_session, session.id)
    freelance_rows = [f for f in all_rows if f.flag_code == "FREELANCE_INCOME_DETECTED"]
    assert len(freelance_rows) == 1  # one row throughout, never duplicated
    assert freelance_rows[0].is_active is True
    assert "FREELANCE_INCOME_DETECTED" in _active_codes(db_session, session.id)


def test_idempotent_retry_creates_no_duplicate_effects(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "idempotent-decision@example.com")
    q1 = questions["has_freelance_income"]

    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)
    flags_after_first = filing_flag_repo.get_all_flags_for_session(db_session, session.id)

    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)  # exact retry
    flags_after_retry = filing_flag_repo.get_all_flags_for_session(db_session, session.id)

    assert len(flags_after_first) == len(flags_after_retry)
    assert {f.id for f in flags_after_first} == {f.id for f in flags_after_retry}
    assert _active_codes(db_session, session.id) == {"FREELANCE_INCOME_DETECTED"}
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED


def test_changed_answer_removes_stale_effects(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "stale@example.com")
    q1 = questions["has_freelance_income"]

    questionnaire_service.submit_answer(db_session, session.id, q1.id, True)
    assert "FREELANCE_INCOME_DETECTED" in _active_codes(db_session, session.id)
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED

    # User changes their mind: no freelance income after all.
    questionnaire_service.submit_answer(db_session, session.id, q1.id, False)

    assert "FREELANCE_INCOME_DETECTED" not in _active_codes(db_session, session.id)
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.UNDETERMINED

    # The flag row still exists (for auditability of when it was active) but is inactive.
    all_flags = filing_flag_repo.get_all_flags_for_session(db_session, session.id)
    freelance_flag = next(f for f in all_flags if f.flag_code == "FREELANCE_INCOME_DETECTED")
    assert freelance_flag.is_active is False


def test_shared_support_survives_partial_removal(db_session, decision_fixture):
    """The exact scenario from the task spec: two facts support the same
    effective state; removing one must not incorrectly clear it."""
    _version, questions = decision_fixture
    session = _make_session(db_session, "sharedsupport@example.com")
    q_freelance = questions["has_freelance_income"]
    q_crypto = questions["has_crypto_income"]

    questionnaire_service.submit_answer(db_session, session.id, q_freelance.id, True)
    questionnaire_service.submit_answer(db_session, session.id, q_crypto.id, True)

    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED  # supported by both

    # Remove freelance support; crypto still supports REVIEW_REQUIRED complexity.
    questionnaire_service.submit_answer(db_session, session.id, q_freelance.id, False)

    db_session.refresh(session)
    assert session.complexity == FilingComplexity.REVIEW_REQUIRED  # NOT cleared — still supported by crypto
    assert "FREELANCE_INCOME_DETECTED" not in _active_codes(db_session, session.id)  # this one had only one supporter

    # Now remove crypto support too -> complexity finally reverts.
    questionnaire_service.submit_answer(db_session, session.id, q_crypto.id, False)
    db_session.refresh(session)
    assert session.complexity == FilingComplexity.UNDETERMINED


def test_shared_support_for_review_required_flag(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "sharedreview@example.com")
    q_crypto = questions["has_crypto_income"]
    q_other = questions["has_other_review_trigger"]

    questionnaire_service.submit_answer(db_session, session.id, q_crypto.id, True)
    questionnaire_service.submit_answer(db_session, session.id, q_other.id, True)
    assert "REVIEW_REQUIRED" in _active_codes(db_session, session.id)

    questionnaire_service.submit_answer(db_session, session.id, q_crypto.id, False)
    assert "REVIEW_REQUIRED" in _active_codes(db_session, session.id)  # still supported by q_other

    questionnaire_service.submit_answer(db_session, session.id, q_other.id, False)
    assert "REVIEW_REQUIRED" not in _active_codes(db_session, session.id)


def test_no_unrelated_workflow_state_destroyed(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "unrelated@example.com")

    # Establish some pre-existing state unrelated to the decision engine.
    original_status = session.status
    original_assessment_year = session.assessment_year
    original_user_id = session.user_id

    questionnaire_service.submit_answer(db_session, session.id, questions["has_freelance_income"].id, True)
    questionnaire_service.submit_answer(db_session, session.id, questions["has_crypto_income"].id, True)

    db_session.refresh(session)
    assert session.status == original_status
    assert session.assessment_year == original_assessment_year
    assert session.user_id == original_user_id

    # A second, unrelated flag-bearing answer must not disturb the first flag.
    questionnaire_service.submit_answer(db_session, session.id, questions["has_other_review_trigger"].id, True)
    assert "FREELANCE_INCOME_DETECTED" in _active_codes(db_session, session.id)


def test_end_flow_stops_progression_but_reconciliation_still_reflects_answers(db_session, decision_fixture):
    _version, questions = decision_fixture
    session = _make_session(db_session, "endflow@example.com")

    questionnaire_service.submit_answer(db_session, session.id, questions["has_freelance_income"].id, True)
    questionnaire_service.submit_answer(db_session, session.id, questions["confirm_end"].id, True)

    next_question = questionnaire_service.get_current_question(db_session, session.id)
    assert next_question is None  # progression terminated by END_FLOW

    # Decision state from answers given before the flow ended is still intact.
    assert "FREELANCE_INCOME_DETECTED" in _active_codes(db_session, session.id)


def test_cross_questionnaire_safety(db_session, decision_fixture):
    """Two independent filing sessions on two independent questionnaire
    versions must never leak decision state into each other."""
    from app.models.enums import QuestionType, RuleAction, RuleConditionOperator
    from app.repositories import questionnaire as repo

    _version_a, questions_a = decision_fixture
    session_a = _make_session(db_session, "crossa@example.com")

    version_b = repo.create_questionnaire_version(db_session, assessment_year="2027-28", version_number=1)
    qb1 = repo.add_question(
        db_session, version_b, key="has_freelance_income", order_index=1,
        question_type=QuestionType.BOOLEAN, prompt="Freelance income (year B)?",
    )
    repo.add_question_rule(
        db_session, qb1, action=RuleAction.SET_PROFILE_FLAG, condition_operator=RuleConditionOperator.EQUALS,
        condition_value=True, action_payload={"flag": "OTHER_VERSION_FLAG"},
    )
    repo.publish_questionnaire_version(db_session, version_b)
    session_b = create_filing_session(
        db_session, FilingSessionCreate(user_id=create_user(db_session, UserCreate(email="crossb@example.com", password="TestPassword123!")).id, assessment_year="2027-28")
    )

    questionnaire_service.submit_answer(db_session, session_a.id, questions_a["has_freelance_income"].id, True)
    questionnaire_service.submit_answer(db_session, session_b.id, qb1.id, True)

    assert _active_codes(db_session, session_a.id) == {"FREELANCE_INCOME_DETECTED"}
    assert _active_codes(db_session, session_b.id) == {"OTHER_VERSION_FLAG"}
