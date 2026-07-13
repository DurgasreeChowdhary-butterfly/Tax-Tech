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
    user = create_user(db_session, UserCreate(email="api@example.com"))
    session = create_filing_session(db_session, FilingSessionCreate(user_id=user.id, assessment_year="2026-27"))
    return session.id


def test_full_question_answer_next_question_workflow(client, questionnaire_fixture, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"

    current = client.get(f"{base}/current")
    assert current.status_code == 200
    body = current.json()
    assert body["question"]["key"] == "has_other_income"
    assert body["is_complete"] is False

    progress = client.get(f"{base}/progress")
    assert progress.status_code == 200
    assert progress.json() == {"total_questions": 5, "answered_questions": 0, "is_complete": False}

    # Answer Q1 = False -> Q2 should be skipped, so next is Q3 (filing_intent)
    answer_resp = client.post(f"{base}/answers", json={"question_id": body["question"]["id"], "value": False})
    assert answer_resp.status_code == 200
    answer_body = answer_resp.json()
    assert answer_body["next_question"]["key"] == "filing_intent"
    assert answer_body["is_complete"] is False

    # Answer Q3 = QUICK -> should jump straight to Q5 (confirm_ready), skipping Q4
    q3_id = answer_body["next_question"]["id"]
    answer_resp = client.post(f"{base}/answers", json={"question_id": q3_id, "value": "QUICK"})
    assert answer_resp.status_code == 200
    answer_body = answer_resp.json()
    assert answer_body["next_question"]["key"] == "confirm_ready"

    # Answer Q5 -> questionnaire complete
    q5_id = answer_body["next_question"]["id"]
    answer_resp = client.post(f"{base}/answers", json={"question_id": q5_id, "value": True})
    assert answer_resp.status_code == 200
    answer_body = answer_resp.json()
    assert answer_body["next_question"] is None
    assert answer_body["is_complete"] is True

    final_progress = client.get(f"{base}/progress")
    assert final_progress.json()["is_complete"] is True

    final_current = client.get(f"{base}/current")
    assert final_current.json() == {"question": None, "is_complete": True}


def test_exact_retry_is_idempotent_via_api(client, questionnaire_fixture, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    current = client.get(f"{base}/current").json()
    question_id = current["question"]["id"]

    first = client.post(f"{base}/answers", json={"question_id": question_id, "value": True})
    second = client.post(f"{base}/answers", json={"question_id": question_id, "value": True})

    assert first.json()["answer"]["id"] == second.json()["answer"]["id"]


def test_invalid_answer_returns_400(client, questionnaire_fixture, filing_session_id):
    base = f"/api/v1/filing-sessions/{filing_session_id}/questionnaire"
    current = client.get(f"{base}/current").json()
    question_id = current["question"]["id"]  # BOOLEAN question

    response = client.post(f"{base}/answers", json={"question_id": question_id, "value": "not-a-boolean"})
    assert response.status_code == 400


def test_unknown_filing_session_returns_404(client, questionnaire_fixture):
    import uuid

    response = client.get(f"/api/v1/filing-sessions/{uuid.uuid4()}/questionnaire/current")
    assert response.status_code == 404
