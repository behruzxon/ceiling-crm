"""
shared.config.settings
~~~~~~~~~~~~~~~~~~~~~~
Application-wide configuration loaded from environment variables.

Usage:
    from shared.config import get_settings
    settings = get_settings()
    print(settings.bot.token)

The settings object is cached via @lru_cache — safe to call get_settings()
repeatedly without performance penalty.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────────────────────
# Sub-settings groups (nested models)
# ─────────────────────────────────────────────────────────────────────────────


class BotSettings(BaseSettings):
    """Telegram bot configuration."""

    model_config = SettingsConfigDict(env_prefix="BOT_", env_file=".env", extra="ignore")

    token: SecretStr = Field(..., description="Telegram Bot API token")
    webhook_url: str | None = Field(default=None, description="Webhook URL (None = polling)")
    webhook_secret: SecretStr | None = Field(default=None)
    admin_group_id: int = Field(..., description="Telegram chat_id of the admin group")
    admin_user_id: int | None = Field(default=None, description="Telegram user_id for DM operator alerts (ADMIN_USER_ID)")
    support_chat_id: int | None = Field(default=None)

    # Telegram API limits
    max_connections: int = Field(default=40, ge=1, le=100)
    parse_mode: str = Field(default="HTML")


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="ceilingcrm")
    password: SecretStr = Field(...)
    db: str = Field(default="ceilingcrm")
    pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=50)
    pool_timeout: int = Field(default=30)
    echo: bool = Field(default=False, description="SQLAlchemy query echo (dev only)")

    @computed_field  # type: ignore[misc]
    @property
    def async_url(self) -> str:
        """Async DSN for SQLAlchemy asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sync_url(self) -> str:
        """Sync DSN for Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class RedisSettings(BaseSettings):
    """Redis connection configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: SecretStr | None = Field(default=None)
    db: int = Field(default=0, description="Main cache DB")
    celery_db: int = Field(default=1, description="Celery broker DB")
    sessions_db: int = Field(default=2, description="FSM state storage DB")

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        """Redis URL for main cache."""
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    @computed_field  # type: ignore[misc]
    @property
    def celery_url(self) -> str:
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.celery_db}"

    @computed_field  # type: ignore[misc]
    @property
    def sessions_url(self) -> str:
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.sessions_db}"


class OpenAISettings(BaseSettings):
    """OpenAI API configuration for AI support assistant."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_", env_file=".env", extra="ignore")

    api_key: SecretStr = Field(...)
    model: str = Field(default="gpt-4o")
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)


class AISettings(BaseSettings):
    """AI provider settings (overrides OpenAI defaults when set)."""

    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    provider: str = Field(default="openai", description="AI provider name")
    api_key: SecretStr | None = Field(default=None, description="Overrides OPENAI_API_KEY if set")
    model: str = Field(default="gpt-4o", description="Model identifier")


class SentrySettings(BaseSettings):
    """Sentry error tracking configuration."""

    model_config = SettingsConfigDict(env_prefix="SENTRY_", env_file=".env", extra="ignore")

    dsn: str | None = Field(default=None)
    traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    environment: str = Field(default="development")


class StorageSettings(BaseSettings):
    """File storage configuration (local or S3)."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    backend: Literal["local", "s3"] = Field(default="local", alias="STORAGE_BACKEND")
    local_path: Path = Field(default=Path("/app/media"), alias="STORAGE_LOCAL_PATH")
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: SecretStr | None = Field(default=None)
    aws_bucket_name: str | None = Field(default=None)
    aws_region: str = Field(default="us-east-1")


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", env_file=".env", extra="ignore")

    window_seconds: int = Field(default=60)
    max_requests: int = Field(default=30, description="Per user per window")


class PaymentSettings(BaseSettings):
    """Payment card requisites shown to clients before they transfer money."""

    model_config = SettingsConfigDict(env_prefix="PAYMENT_", env_file=".env", extra="ignore")

    card_number: str | None = Field(default=None, description="Card number digits, e.g. 8600123456781234")
    card_holder: str | None = Field(default=None, description="Cardholder full name")
    bank_name: str | None = Field(default=None, description="Bank name shown in requisites")


class BusinessSettings(BaseSettings):
    """Business rules and defaults."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    currency: str = Field(default="UZS", alias="CURRENCY")
    default_language: str = Field(default="uz", alias="DEFAULT_LANGUAGE")
    supported_languages: list[str] = Field(default=["uz", "ru", "en"], alias="SUPPORTED_LANGUAGES")
    follow_up_day1_hours: int = Field(default=24, alias="FOLLOW_UP_DAY1_HOURS")
    follow_up_day3_hours: int = Field(default=72, alias="FOLLOW_UP_DAY3_HOURS")
    follow_up_day7_hours: int = Field(default=168, alias="FOLLOW_UP_DAY7_HOURS")
    new_lead_alert_minutes: int = Field(default=30, alias="NEW_LEAD_ALERT_MINUTES")
    broadcast_rate_limit: int = Field(default=30, alias="BROADCAST_RATE_LIMIT")


# ─────────────────────────────────────────────────────────────────────────────
# Root Settings (aggregates sub-settings)
# ─────────────────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """
    Root application settings.

    Sub-settings are lazily instantiated.
    Call get_settings() to get a cached singleton.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_debug: bool = Field(default=False)
    app_secret_key: SecretStr = Field(...)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    # Prometheus
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)

    # Nested settings (instantiated from env in validators)
    bot: BotSettings = Field(default_factory=BotSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    ai: AISettings = Field(default_factory=AISettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    business: BusinessSettings = Field(default_factory=BusinessSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce production-specific requirements."""
        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("DEBUG must be False in production")
            if not self.bot.webhook_url:
                raise ValueError("BOT_WEBHOOK_URL is required in production")
            if not self.sentry.dsn:
                raise ValueError("SENTRY_DSN is required in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    The cache is invalidated only on process restart.
    In tests, call get_settings.cache_clear() before patching env vars.
    """
    return Settings()
