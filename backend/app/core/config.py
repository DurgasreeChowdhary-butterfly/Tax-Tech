from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match Settings.jwt_secret_key's default exactly — see the
# model_validator below, which refuses to let this specific placeholder
# reach a non-development environment.
_INSECURE_DEFAULT_JWT_SECRET_KEY = "dev-only-insecure-secret-override-via-env-JWT_SECRET_KEY"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ITR Filing API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/itr_filing"

    # Private document storage. Local filesystem only for now — see
    # app/integrations/storage for the provider abstraction.
    document_storage_root: str = "./var/document_storage"
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Phase 11 auth (JWT). Dev-only default secret — MUST be overridden via
    # the JWT_SECRET_KEY env var in any real deployment; never commit a real
    # secret here. Access tokens are short-lived; refresh tokens are longer-
    # lived and individually revocable (see app/models/refresh_token.py).
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @model_validator(mode="after")
    def _reject_insecure_jwt_secret_outside_development(self) -> "Settings":
        """Fail fast at startup rather than silently signing tokens with a
        secret published in this repo's source history. `environment` is the
        only signal this app has for "am I in production" — anything other
        than the literal "development" is treated as not-safe-for-the-
        placeholder-secret, so a deployment that simply forgets to set
        JWT_SECRET_KEY refuses to boot instead of running insecurely.
        """
        if self.environment != "development" and self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET_KEY:
            raise ValueError(
                "jwt_secret_key is still the insecure development default while "
                f"environment={self.environment!r} (not 'development'). Set the JWT_SECRET_KEY "
                "environment variable to a real secret before running in this environment."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
