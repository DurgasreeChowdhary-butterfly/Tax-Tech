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
