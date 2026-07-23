from dataclasses import dataclass

from app.engines.decision.resolver import REVIEW_REQUIRED_FLAG
from app.models.enums import FilerCategory, FilingComplexity, ResidencyStatus, SupportedCaseOutcome

# Closed vocabulary of filing_flag codes the Supported Case Validator treats as
# putting a case outside V1 scope entirely (docs/PRODUCT_SCOPE.md excluded
# list). These flags are set by the Decision Engine (Phase 4) from a published
# questionnaire version's SET_PROFILE_FLAG rules; the tax engine only reads
# their (fixed, non-sensitive) codes here, never questionnaire answer content.
UNSUPPORTED_SCENARIO_FLAG_CODES = frozenset(
    {
        "FREELANCE_INCOME_DETECTED",
        "BUSINESS_INCOME_DETECTED",
        "CAPITAL_GAINS_UNSUPPORTED_DETECTED",
        "CRYPTO_INCOME_DETECTED",
        "FOREIGN_INCOME_DETECTED",
    }
)

_UNSUPPORTED_RESIDENCY_STATUSES = frozenset(
    {ResidencyStatus.RESIDENT_NOT_ORDINARILY_RESIDENT, ResidencyStatus.NON_RESIDENT}
)


@dataclass(frozen=True)
class SupportedCaseInput:
    """Facts the Supported Case Validator needs. Every field here must be
    sourced from either the filing_session record itself or a VERIFIED domain
    table (salary_income/interest_income) or filing_flags — never from raw
    extracted_fields/document_extractions (docs/TAX_ENGINE_BOUNDARY.md)."""

    filer_category: FilerCategory | None
    residency_status: ResidencyStatus | None
    session_complexity: FilingComplexity
    active_flag_codes: frozenset[str]
    has_published_rule_set: bool
    has_verified_income: bool


@dataclass(frozen=True)
class SupportedCaseResult:
    outcome: SupportedCaseOutcome
    reasons: tuple[str, ...]  # fixed, safe reason codes only — never free text


def evaluate_supported_case(inputs: SupportedCaseInput) -> SupportedCaseResult:
    """Pure, deterministic classification. Runs before any calculation
    (docs/TAX_ENGINE_BOUNDARY.md). Precedence, most severe first: NOT_SUPPORTED
    > REVIEW_REQUIRED > INCOMPLETE > SUPPORTED — a scenario that is
    fundamentally out of scope must never be downgraded to merely "incomplete"
    just because some other input also happens to be missing.
    """
    not_supported_reasons: list[str] = []
    if not inputs.has_published_rule_set:
        not_supported_reasons.append("NO_PUBLISHED_RULE_SET")
    if inputs.filer_category == FilerCategory.OTHER:
        not_supported_reasons.append("FILER_CATEGORY_UNSUPPORTED")
    if inputs.residency_status in _UNSUPPORTED_RESIDENCY_STATUSES:
        not_supported_reasons.append("RESIDENCY_STATUS_UNSUPPORTED")
    unsupported_flags_active = sorted(inputs.active_flag_codes & UNSUPPORTED_SCENARIO_FLAG_CODES)
    for flag_code in unsupported_flags_active:
        not_supported_reasons.append(f"UNSUPPORTED_SCENARIO:{flag_code}")
    if inputs.session_complexity == FilingComplexity.NOT_SUPPORTED:
        not_supported_reasons.append("COMPLEXITY_NOT_SUPPORTED")

    if not_supported_reasons:
        return SupportedCaseResult(SupportedCaseOutcome.NOT_SUPPORTED, tuple(not_supported_reasons))

    review_reasons: list[str] = []
    if inputs.session_complexity == FilingComplexity.REVIEW_REQUIRED:
        review_reasons.append("COMPLEXITY_REVIEW_REQUIRED")
    if REVIEW_REQUIRED_FLAG in inputs.active_flag_codes:
        review_reasons.append("REVIEW_REQUIRED_FLAG_ACTIVE")

    if review_reasons:
        return SupportedCaseResult(SupportedCaseOutcome.REVIEW_REQUIRED, tuple(review_reasons))

    incomplete_reasons: list[str] = []
    if inputs.filer_category is None:
        incomplete_reasons.append("FILER_CATEGORY_MISSING")
    if inputs.residency_status is None:
        incomplete_reasons.append("RESIDENCY_STATUS_MISSING")
    if not inputs.has_verified_income:
        incomplete_reasons.append("NO_VERIFIED_INCOME")

    if incomplete_reasons:
        return SupportedCaseResult(SupportedCaseOutcome.INCOMPLETE, tuple(incomplete_reasons))

    return SupportedCaseResult(SupportedCaseOutcome.SUPPORTED, tuple())
