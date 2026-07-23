import uuid
from decimal import Decimal

import pytest

from app.engines.tax.errors import InvalidDeductionValueError, UnsupportedDeductionCodeError
from app.repositories import deduction as deduction_repo
from app.services import deduction as deduction_service


def test_claim_deduction_persists(db_session, uploaded_document):
    filing_session, _tax_document = uploaded_document
    claim = deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    assert claim.claimed_amount == Decimal("150000.00")


def test_claim_unsupported_code_rejected_no_write(db_session, uploaded_document):
    filing_session, _tax_document = uploaded_document
    with pytest.raises(UnsupportedDeductionCodeError):
        deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80D", "10000.00")
    assert deduction_repo.list_deduction_claims_for_session(db_session, filing_session.id) == []


def test_claim_invalid_amount_rejected_no_write(db_session, uploaded_document):
    filing_session, _tax_document = uploaded_document
    with pytest.raises(InvalidDeductionValueError):
        deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "-500.00")
    assert deduction_repo.list_deduction_claims_for_session(db_session, filing_session.id) == []


def test_reclaim_same_amount_is_idempotent(db_session, uploaded_document):
    filing_session, _tax_document = uploaded_document
    first = deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    second = deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    assert first.id == second.id
    assert first.updated_at == second.updated_at


def test_reclaim_different_amount_updates_in_place(db_session, uploaded_document):
    filing_session, _tax_document = uploaded_document
    first = deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "150000.00")
    second = deduction_service.claim_deduction(db_session, filing_session.id, "SECTION_80C", "100000.00")
    assert first.id == second.id
    assert second.claimed_amount == Decimal("100000.00")


def test_unknown_filing_session_rejected(db_session):
    with pytest.raises(ValueError):
        deduction_service.claim_deduction(db_session, uuid.uuid4(), "SECTION_80C", "150000.00")
