import re

from app.models.enums import FilerCategory, ResidencyStatus, VerificationAction
from app.repositories import tax_calculation as tax_calculation_repo
from app.repositories.filing_session import update_filing_session
from app.schemas.filing_session import FilingSessionUpdate
from app.services import tax_calculation as tax_calculation_service
from app.services import verification as verification_service
from app.tests.conftest import auth_headers

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _supported_session(db_session, extracted_document, gross_salary="1000000.00", tds="50000.00"):
    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    update_filing_session(
        db_session, filing_session,
        FilingSessionUpdate(residency_status=ResidencyStatus.RESIDENT, filer_category=FilerCategory.SALARIED),
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["gross_salary"].id,
        action=VerificationAction.CORRECT, value=gross_salary,
    )
    verification_service.verify_field(
        db_session, filing_session.id, tax_document.id, fields_by_name["tds_deducted"].id,
        action=VerificationAction.CORRECT, value=tds,
    )
    return filing_session, tax_document, fields_by_name


def test_input_fingerprint_is_a_sha256_digest_not_reversible_payload(db_session, extracted_document, real_fy2025_26_rule_set):
    from app.models.enums import TaxRegime

    filing_session, *_ = _supported_session(db_session, extracted_document)
    tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    calc = tax_calculation_repo.get_current_calculation(db_session, filing_session.id, TaxRegime.NEW)
    assert _SHA256_HEX_RE.match(calc.input_fingerprint)
    # A cryptographic digest must not literally contain any of the plaintext
    # amounts it was derived from.
    assert "1000000" not in calc.input_fingerprint
    assert "925000" not in calc.input_fingerprint
    assert "50000" not in calc.input_fingerprint


def test_pan_field_never_confirmed_never_enters_calculation(db_session, extracted_document, real_fy2025_26_rule_set):
    """The extracted `pan` candidate is never confirmable (Phase 7) and is
    never read by any Phase 9 code path — calculating tax must succeed
    without ever touching it, and no PAN value ever appears in the
    calculation's persisted figures/fingerprint."""
    from app.models.enums import TaxRegime

    filing_session, tax_document, fields_by_name = _supported_session(db_session, extracted_document)
    pan_value = fields_by_name["pan"].raw_value
    assert pan_value  # sanity: the mock extraction really produced one

    calc, line_items = tax_calculation_service.calculate_tax(db_session, filing_session.id, TaxRegime.NEW)

    serialized = "".join(
        [
            calc.input_fingerprint,
            str(calc.gross_total_income),
            str(calc.taxable_income),
            str(calc.total_tax_liability),
        ]
    )
    for li in line_items:
        serialized += li.step_code + str(li.amount)
    assert pan_value not in serialized


def test_calculation_error_responses_never_leak_raw_exception_text(client, db_session, extracted_document, real_fy2025_26_rule_set):
    """Triggering the surcharge guard (an internal engine exception) via the
    API must surface only the safe HTTPException detail — never a raw
    traceback, file path, or internals beyond the already-safe message the
    error class itself constructs."""
    filing_session, tax_document, fields_by_name = _supported_session(
        db_session, extracted_document, gross_salary="6000000.00", tds="0.00"
    )
    client.headers.update(auth_headers(filing_session.user_id))

    resp = client.get(f"/api/v1/filing-sessions/{filing_session.id}/calculations/NEW")
    assert resp.status_code == 409
    body_text = resp.text
    assert "Traceback" not in body_text
    assert ".py" not in body_text
    assert "app/engines" not in body_text and "app\\engines" not in body_text
