import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.repositories.filing_session import create_filing_session
from app.repositories.user import create_user
from app.schemas.filing_session import FilingSessionCreate
from app.schemas.user import UserCreate


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def filing_session_id(db_session):
    user = create_user(db_session, UserCreate(email="decision-api@example.com"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    return session.id


def test_full_api_flow_from_answer_to_decision_state(client, decision_fixture, filing_session_id):
    _version, questions = decision_fixture
    q_base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    d_base = f"/api/v1/filing-sessions/{filing_session_id}/decision-state"

    initial = client.get(d_base).json()
    assert initial == {"complexity": "UNDETERMINED", "flags": []}

    answer_resp = client.post(
        f"{q_base}/answers", json={"question_id": str(questions["has_freelance_income"].id), "value": True}
    )
    assert answer_resp.status_code == 200

    state = client.get(d_base).json()
    assert state["complexity"] == "REVIEW_REQUIRED"
    flag_codes = {f["flag_code"]: f["is_active"] for f in state["flags"]}
    assert flag_codes["FREELANCE_INCOME_DETECTED"] is True

    # Change the answer -> reconciliation clears the flag and complexity via the API.
    client.post(f"{q_base}/answers", json={"question_id": str(questions["has_freelance_income"].id), "value": False})

    state = client.get(d_base).json()
    assert state["complexity"] == "UNDETERMINED"
    flag_codes = {f["flag_code"]: f["is_active"] for f in state["flags"]}
    assert flag_codes["FREELANCE_INCOME_DETECTED"] is False


def test_shared_support_via_api(client, decision_fixture, filing_session_id):
    _version, questions = decision_fixture
    q_base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    d_base = f"/api/v1/filing-sessions/{filing_session_id}/decision-state"

    client.post(f"{q_base}/answers", json={"question_id": str(questions["has_crypto_income"].id), "value": True})
    client.post(f"{q_base}/answers", json={"question_id": str(questions["has_other_review_trigger"].id), "value": True})

    state = client.get(d_base).json()
    flags = {f["flag_code"]: f["is_active"] for f in state["flags"]}
    assert flags["REVIEW_REQUIRED"] is True

    client.post(f"{q_base}/answers", json={"question_id": str(questions["has_crypto_income"].id), "value": False})
    state = client.get(d_base).json()
    flags = {f["flag_code"]: f["is_active"] for f in state["flags"]}
    assert flags["REVIEW_REQUIRED"] is True  # still supported by has_other_review_trigger

    client.post(f"{q_base}/answers", json={"question_id": str(questions["has_other_review_trigger"].id), "value": False})
    state = client.get(d_base).json()
    flags = {f["flag_code"]: f["is_active"] for f in state["flags"]}
    assert flags["REVIEW_REQUIRED"] is False


def test_end_flow_via_api(client, decision_fixture, filing_session_id):
    q_base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    _version, questions = decision_fixture

    client.post(f"{q_base}/answers", json={"question_id": str(questions["confirm_end"].id), "value": True})

    current = client.get(f"{q_base}/current").json()
    assert current == {"question": None, "is_complete": True}


def test_idempotent_retry_via_api_no_duplicate_flags(client, decision_fixture, filing_session_id):
    q_base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    d_base = f"/api/v1/filing-sessions/{filing_session_id}/decision-state"
    _version, questions = decision_fixture
    q1_id = str(questions["has_freelance_income"].id)

    client.post(f"{q_base}/answers", json={"question_id": q1_id, "value": True})
    first_state = client.get(d_base).json()

    client.post(f"{q_base}/answers", json={"question_id": q1_id, "value": True})  # exact retry
    second_state = client.get(d_base).json()

    assert first_state == second_state
    assert len(second_state["flags"]) == 1  # no duplicate rows
