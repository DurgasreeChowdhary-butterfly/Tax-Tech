from app.tests.conftest import auth_headers


def test_claim_deduction_via_api(client, uploaded_document):
    filing_session, _tax_document = uploaded_document
    client.headers.update(auth_headers(filing_session.user_id))
    resp = client.post(
        f"/api/v1/filing-sessions/{filing_session.id}/deductions",
        json={"code": "SECTION_80C", "claimed_amount": "150000.00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "SECTION_80C"
    assert body["claimed_amount"] == "150000.00"


def test_claim_unsupported_code_returns_400(client, uploaded_document):
    filing_session, _tax_document = uploaded_document
    client.headers.update(auth_headers(filing_session.user_id))
    resp = client.post(
        f"/api/v1/filing-sessions/{filing_session.id}/deductions",
        json={"code": "SECTION_80D", "claimed_amount": "10000.00"},
    )
    assert resp.status_code == 400


def test_claim_negative_amount_returns_400(client, uploaded_document):
    filing_session, _tax_document = uploaded_document
    client.headers.update(auth_headers(filing_session.user_id))
    resp = client.post(
        f"/api/v1/filing-sessions/{filing_session.id}/deductions",
        json={"code": "SECTION_80C", "claimed_amount": "-1.00"},
    )
    assert resp.status_code == 400


def test_unknown_filing_session_returns_404(client, uploaded_document):
    import uuid

    filing_session, _tax_document = uploaded_document
    client.headers.update(auth_headers(filing_session.user_id))
    resp = client.post(
        f"/api/v1/filing-sessions/{uuid.uuid4()}/deductions",
        json={"code": "SECTION_80C", "claimed_amount": "150000.00"},
    )
    assert resp.status_code == 404
