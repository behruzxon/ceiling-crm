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
    username: str = Field(default="vashpotolokbot", description="Bot @username without @ — used for deep links")
    webhook_url: str | None = Field(default=None, description="Webhook URL (None = polling)")
    webhook_secret: SecretStr | None = Field(default=None)
    admin_group_id: int = Field(..., description="Telegram chat_id of the admin group (for notifications)")
    main_group_id: int | None = Field(default=None, description="Telegram chat_id of the main customer group (for join tracking via BOT_MAIN_GROUP_ID)")
    admin_user_id: int | None = Field(default=None, description="Telegram user_id for DM operator alerts (ADMIN_USER_ID)")
    support_chat_id: int | None = Field(default=None)

    # Runtime
    runtime_mode: str = Field(default="single", description="'single' = one bot from BOT_TOKEN, 'multi' = load tenant bots from DB")

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


class AIRateLimitSettings(BaseSettings):
    """Per-user and per-tenant rate limiting for AI (OpenAI) calls."""

    model_config = SettingsConfigDict(env_prefix="AI_RATE_LIMIT_", env_file=".env", extra="ignore")

    user_window_seconds: int = Field(default=60, description="Per-user sliding window (seconds)")
    user_max_requests: int = Field(default=10, description="Max AI calls per user per window")
    tenant_daily_limit: int = Field(default=5000, description="Max AI calls per tenant per UTC day (0 = unlimited)")


class ClickSettings(BaseSettings):
    """Click.uz payment gateway configuration."""

    model_config = SettingsConfigDict(env_prefix="CLICK_", env_file=".env", extra="ignore")

    merchant_id: int | None = Field(default=None, description="Click merchant ID")
    service_id: int | None = Field(default=None, description="Click service ID")
    secret_key: SecretStr | None = Field(default=None, description="Click secret key for signature verification")
    merchant_user_id: int | None = Field(default=None, description="Click merchant user ID")

    @property
    def is_configured(self) -> bool:
        return all([self.merchant_id, self.service_id, self.secret_key])


class PaymeSettings(BaseSettings):
    """Payme.uz payment gateway configuration."""

    model_config = SettingsConfigDict(env_prefix="PAYME_", env_file=".env", extra="ignore")

    merchant_id: str | None = Field(default=None, description="Payme merchant ID")
    merchant_key: SecretStr | None = Field(default=None, description="Payme merchant key for auth + signature")
    test_mode: bool = Field(default=True, description="Use Payme test environment")

    @property
    def is_configured(self) -> bool:
        return all([self.merchant_id, self.merchant_key])

    @property
    def checkout_base_url(self) -> str:
        if self.test_mode:
            return "https://test.paycom.uz"
        return "https://checkout.paycom.uz"


class PaymentSettings(BaseSettings):
    """Payment card requisites shown to clients before they transfer money."""

    model_config = SettingsConfigDict(env_prefix="PAYMENT_", env_file=".env", extra="ignore")

    card_number: str | None = Field(default=None, description="Card number digits, e.g. 8600123456781234")
    card_holder: str | None = Field(default=None, description="Cardholder full name")
    bank_name: str | None = Field(default=None, description="Bank name shown in requisites")


class CTASettings(BaseSettings):
    """CTA (call-to-action) marketing prompts configuration."""

    model_config = SettingsConfigDict(env_prefix="CTA_", env_file=".env", extra="ignore")

    enabled: bool = Field(default=True, description="Master switch — set false to suppress all CTA messages")
    discount_text: str = Field(
        default="🔥 Chegirma aktiv! Bugun -10% (shartlar operator orqali)",
        description="Text sent with the discount CTA inline keyboard",
    )
    discount_percent: int | None = Field(
        default=None,
        description="When set, appended to the discount button label as '(-N%)'",
    )


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
    bot_token_encryption_key: SecretStr = Field(
        default=SecretStr(""),
        description="Fernet key for encrypting tenant bot tokens at rest",
    )
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
    ai_rate_limit: AIRateLimitSettings = Field(default_factory=AIRateLimitSettings)
    business: BusinessSettings = Field(default_factory=BusinessSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    cta: CTASettings = Field(default_factory=CTASettings)
    click: ClickSettings = Field(default_factory=ClickSettings)
    payme: PaymeSettings = Field(default_factory=PaymeSettings)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce production-specific requirements.

        In production mode, fail-fast on missing or placeholder secrets.
        In staging mode, emit warnings via stderr (non-blocking).
        """
        _PLACEHOLDER_SECRETS = frozenset({
            "change-me-to-random-64-char-secret",
            "change-me-random-webhook-secret",
            "change-me-strong-password",
            "sk-proj-...",
        })

        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("APP_DEBUG must be False in production")
            if not self.bot.webhook_url:
                raise ValueError("BOT_WEBHOOK_URL is required in production")
            if not self.sentry.dsn:
                raise ValueError("SENTRY_DSN is required in production")

            # Secrets must not be placeholders
            secret_key = self.app_secret_key.get_secret_value()
            if secret_key in _PLACEHOLDER_SECRETS:
                raise ValueError(
                    "APP_SECRET_KEY is still a placeholder — generate a real secret"
                )
            if len(secret_key) < 32:
                raise ValueError(
                    "APP_SECRET_KEY must be at least 32 characters in production"
                )
            enc_key = self.bot_token_encryption_key.get_secret_value()
            if not enc_key or len(enc_key) < 16:
                raise ValueError(
                    "BOT_TOKEN_ENCRYPTION_KEY is required in production "
                    "(min 16 chars). Generate with: "
                    "python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                )
            if self.db.password.get_secret_value() in _PLACEHOLDER_SECRETS:
                raise ValueError(
                    "POSTGRES_PASSWORD is still a placeholder — set a strong password"
                )
            if len(self.db.password.get_secret_value()) < 12:
                raise ValueError(
                    "POSTGRES_PASSWORD must be at least 12 characters in production"
                )
            if self.openai.api_key.get_secret_value() in _PLACEHOLDER_SECRETS:
                raise ValueError(
                    "OPENAI_API_KEY is still a placeholder — set a real API key"
                )
            if not self.bot.admin_group_id:
                raise ValueError(
                    "BOT_ADMIN_GROUP_ID is required in production"
                )
            # Webhook secret is required in production (webhook mode)
            if not self.bot.webhook_secret:
                raise ValueError(
                    "BOT_WEBHOOK_SECRET is required in production for webhook verification"
                )
            if self.bot.webhook_secret.get_secret_value() in _PLACEHOLDER_SECRETS:
                raise ValueError(
                    "BOT_WEBHOOK_SECRET is still a placeholder — generate a random string"
                )
            # Redis should have a password in production
            if not self.redis.password:
                import sys
                print(
                    "WARNING: REDIS_PASSWORD is empty in production — "
                    "set a password for Redis auth",
                    file=sys.stderr,
                )

        elif self.app_env == "staging":
            import sys
            if self.app_secret_key.get_secret_value() in _PLACEHOLDER_SECRETS:
                print(
                    "WARNING: APP_SECRET_KEY is a placeholder in staging",
                    file=sys.stderr,
                )
            if self.db.password.get_secret_value() in _PLACEHOLDER_SECRETS:
                print(
                    "WARNING: POSTGRES_PASSWORD is a placeholder in staging",
                    file=sys.stderr,
                )

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
