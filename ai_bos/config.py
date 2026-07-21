"""Central configuration — fail fast if any required secret is missing."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — accepts PostgreSQL URLs in production and SQLite for tests
    database_url: str

    # Redis / Celery
    redis_url: str

    # AI
    anthropic_api_key: SecretStr

    # Communication
    sendgrid_api_key: SecretStr
    sendgrid_from_email: str
    twilio_account_sid: SecretStr
    twilio_auth_token: SecretStr
    twilio_from_phone: str

    # Payments
    stripe_secret_key: SecretStr
    stripe_webhook_secret: SecretStr

    # Encryption
    encryption_key: SecretStr

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def anthropic_key(self) -> str:
        return self.anthropic_api_key.get_secret_value()


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
