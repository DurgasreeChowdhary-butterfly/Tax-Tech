import enum


class ResidencyStatus(str, enum.Enum):
    RESIDENT = "RESIDENT"
    RESIDENT_NOT_ORDINARILY_RESIDENT = "RESIDENT_NOT_ORDINARILY_RESIDENT"
    NON_RESIDENT = "NON_RESIDENT"


class FilerCategory(str, enum.Enum):
    SALARIED = "SALARIED"
    OTHER = "OTHER"


class FilingSessionStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class FilingComplexity(str, enum.Enum):
    UNDETERMINED = "UNDETERMINED"
    SIMPLE = "SIMPLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class QuestionnaireVersionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTI_CHOICE = "MULTI_CHOICE"
    BOOLEAN = "BOOLEAN"
    CURRENCY = "CURRENCY"
    NUMBER = "NUMBER"
    DATE = "DATE"
    TEXT = "TEXT"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    INFORMATION = "INFORMATION"
    REVIEW_CARD = "REVIEW_CARD"


class RuleConditionOperator(str, enum.Enum):
    ALWAYS = "ALWAYS"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    IN = "IN"


class RuleAction(str, enum.Enum):
    SHOW_QUESTION = "SHOW_QUESTION"
    SKIP_QUESTION = "SKIP_QUESTION"
    GO_TO_QUESTION = "GO_TO_QUESTION"
    SET_PROFILE_FLAG = "SET_PROFILE_FLAG"
    SET_COMPLEXITY = "SET_COMPLEXITY"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    END_FLOW = "END_FLOW"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    DELETED = "DELETED"


class StorageProviderName(str, enum.Enum):
    LOCAL_FILESYSTEM = "LOCAL_FILESYSTEM"


class DocumentProcessingJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExtractionProviderName(str, enum.Enum):
    MOCK = "MOCK"


class ExtractionFailureCode(str, enum.Enum):
    """Small, fixed, API-safe classification of why a processing job failed.
    Never derived from raw exception text — see
    app/engines/extraction/failure_classification.py."""

    STORAGE_OBJECT_MISSING = "STORAGE_OBJECT_MISSING"
    STORAGE_ERROR = "STORAGE_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class VerificationAction(str, enum.Enum):
    CONFIRM = "CONFIRM"
    CORRECT = "CORRECT"


class TaxRuleSetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class TaxRegime(str, enum.Enum):
    OLD = "OLD"
    NEW = "NEW"


class TaxRuleType(str, enum.Enum):
    SLAB = "SLAB"
    REBATE = "REBATE"
    SURCHARGE = "SURCHARGE"
    CESS = "CESS"
    DEDUCTION = "DEDUCTION"


class SupportedCaseOutcome(str, enum.Enum):
    """Supported Case Validator outcomes (docs/TAX_ENGINE_BOUNDARY.md). Only
    SUPPORTED proceeds to calculation (Phase 9); the other three block
    calculation and surface a filing_flag instead of a number."""

    SUPPORTED = "SUPPORTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCOMPLETE = "INCOMPLETE"


class ConsentDefinitionStatus(str, enum.Enum):
    """Mirrors QuestionnaireVersionStatus/TaxRuleSetStatus: DRAFT rows may be
    edited freely; PUBLISHED rows are immutable (docs/DATA_MODEL.md)."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class UserConsentStatus(str, enum.Enum):
    """One value per user_consents row — the action that row records, not a
    mutable "current state" field. ACCEPTED and WITHDRAWN rows accumulate as
    append-only history (see app/models/user_consent.py)."""

    ACCEPTED = "ACCEPTED"
    WITHDRAWN = "WITHDRAWN"


class ActorType(str, enum.Enum):
    """Phase 10 actor model. No auth/JWT exists yet (Phase 11) — USER always
    carries an explicit actor_user_id propagated by the calling service from
    a known domain identity (e.g. filing_session.user_id), never inferred.
    SYSTEM is for actions with no direct originating user request (e.g. an
    async extraction worker's outcome)."""

    USER = "USER"
    SYSTEM = "SYSTEM"


class AuditEventCode(str, enum.Enum):
    """Closed, fixed vocabulary for audit_logs.event_code (docs/DATA_MODEL.md
    "audit_logs" + Phase 10). Every event this system can emit is listed here
    — never a free-form string, so the audit trail stays queryable and
    reviewable. Extend deliberately; do not repurpose an existing code."""

    FILING_SESSION_CREATED = "FILING_SESSION_CREATED"
    QUESTION_ANSWER_CREATED = "QUESTION_ANSWER_CREATED"
    QUESTION_ANSWER_CHANGED = "QUESTION_ANSWER_CHANGED"
    FILING_FLAG_ACTIVATED = "FILING_FLAG_ACTIVATED"
    FILING_FLAG_DEACTIVATED = "FILING_FLAG_DEACTIVATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    EXTRACTED_FIELD_CONFIRMED = "EXTRACTED_FIELD_CONFIRMED"
    EXTRACTED_FIELD_CORRECTED = "EXTRACTED_FIELD_CORRECTED"
    DEDUCTION_CLAIMED = "DEDUCTION_CLAIMED"
    DEDUCTION_CHANGED = "DEDUCTION_CHANGED"
    TAX_CALCULATION_CREATED = "TAX_CALCULATION_CREATED"
    TAX_CALCULATION_RECALCULATED = "TAX_CALCULATION_RECALCULATED"
    CONSENT_ACCEPTED = "CONSENT_ACCEPTED"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
