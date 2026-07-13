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
