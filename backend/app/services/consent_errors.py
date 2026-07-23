class ConsentError(Exception):
    """Base class for consent service domain errors."""


class ConsentDefinitionNotFoundError(ConsentError):
    def __init__(self, code: str):
        super().__init__(f"No published consent definition found for code {code!r}")
        self.code = code


class NoActiveConsentToWithdrawError(ConsentError):
    def __init__(self, code: str):
        super().__init__(f"No accepted consent for code {code!r} to withdraw")
        self.code = code


class MissingRequiredConsentError(ConsentError):
    def __init__(self, missing_codes: list[str]):
        super().__init__(f"Required consent(s) not accepted: {', '.join(missing_codes)}")
        self.missing_codes = missing_codes
