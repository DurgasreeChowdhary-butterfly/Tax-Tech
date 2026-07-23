"""Phase 7 exit criterion: "an unconfirmed extraction cannot be read by the tax
engine layer" — verified as an import/dependency-boundary check (per
docs/IMPLEMENTATION_PLAN.md Phase 7 test list), plus a behavioral proof that
raw extraction alone never produces a domain record and that the protected
PAN identity boundary (docs/DATA_MODEL.md tax_profiles) is respected.
"""

import ast
from pathlib import Path

from app.models.enums import VerificationAction
from app.models.salary_income import SalaryIncome
from app.models.tax_profile import TaxProfile
from app.repositories import verification as verification_repo
from app.services import verification as verification_service

_FORBIDDEN_IMPORT_PREFIXES = (
    "app.models.document_extraction",
    "app.models.extracted_field",
    "app.integrations.ocr",
)


def _imported_module_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_tax_engine_package_does_not_import_raw_extraction_modules():
    tax_engine_dir = Path(__file__).resolve().parents[1] / "engines" / "tax"
    assert tax_engine_dir.is_dir()

    for py_file in tax_engine_dir.rglob("*.py"):
        imported = _imported_module_names(py_file)
        for forbidden in _FORBIDDEN_IMPORT_PREFIXES:
            offending = {name for name in imported if name == forbidden or name.startswith(forbidden + ".")}
            assert not offending, f"{py_file} imports raw-extraction module(s) {offending}"


def test_phase8_supported_case_modules_do_not_import_raw_extraction_modules():
    """Phase 8's service/repository entry points (app/services/supported_case.py,
    app/repositories/income.py) sit right at the extraction-to-tax trust
    boundary — they must read only verified domain tables, never
    extracted_fields/document_extractions/OCR modules directly."""
    repo_root = Path(__file__).resolve().parents[1]
    files_to_check = [
        repo_root / "services" / "supported_case.py",
        repo_root / "repositories" / "income.py",
    ]

    for py_file in files_to_check:
        assert py_file.is_file()
        imported = _imported_module_names(py_file)
        for forbidden in _FORBIDDEN_IMPORT_PREFIXES:
            offending = {name for name in imported if name == forbidden or name.startswith(forbidden + ".")}
            assert not offending, f"{py_file} imports raw-extraction module(s) {offending}"


def test_phase9_calculation_modules_do_not_import_raw_extraction_modules():
    """Phase 9's calculation entry points must read only verified domain
    tables and published tax rule sets — never extracted_fields/
    document_extractions/OCR modules directly."""
    repo_root = Path(__file__).resolve().parents[1]
    files_to_check = [
        repo_root / "services" / "tax_calculation.py",
        repo_root / "services" / "deduction.py",
        repo_root / "repositories" / "tax_calculation.py",
        repo_root / "repositories" / "deduction.py",
    ]

    for py_file in files_to_check:
        assert py_file.is_file()
        imported = _imported_module_names(py_file)
        for forbidden in _FORBIDDEN_IMPORT_PREFIXES:
            offending = {name for name in imported if name == forbidden or name.startswith(forbidden + ".")}
            assert not offending, f"{py_file} imports raw-extraction module(s) {offending}"


def test_unverified_extraction_alone_creates_no_domain_record(db_session, extracted_document):
    """Running extraction (Phase 6) produces raw candidates only — no
    salary_income/interest_income row exists until verify_field runs."""
    _filing_session, _tax_document, _extraction, _fields_by_name = extracted_document
    assert db_session.query(SalaryIncome).count() == 0


def test_protected_pan_field_never_reaches_any_storage_via_verification(db_session, extracted_document):
    """Confirming/correcting the raw `pan` candidate must be rejected outright
    — it must never reach a domain table, and it must never be written into
    the real protected identity column either (tax_profiles.pan_encrypted),
    since Phase 7 does not implement PAN encryption."""
    from app.engines.extraction.errors import UnsupportedFieldMappingError

    filing_session, tax_document, _extraction, fields_by_name = extracted_document
    pan_field = fields_by_name["pan"]

    import pytest

    with pytest.raises(UnsupportedFieldMappingError):
        verification_service.verify_field(
            db_session, filing_session.id, tax_document.id, pan_field.id, action=VerificationAction.CONFIRM
        )

    assert verification_repo.get_current_verification(db_session, pan_field.id) is None
    tax_profile = db_session.query(TaxProfile).filter_by(user_id=filing_session.user_id).first()
    assert tax_profile is None  # nothing was ever created/written for this user's protected identity
