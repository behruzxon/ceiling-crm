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


class ApiSettings(BaseSettings):
    """REST API configuration."""

    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    internal_token: SecretStr | None = Field(
        default=None,
        description="Bearer token for internal API access. "
        "Required in production; optional in development (open access with warning).",
    )


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

    # CRM Operator Reply
    crm_operator_reply_enabled: bool = Field(default=False, alias="CRM_OPERATOR_REPLY_ENABLED")
    crm_operator_reply_max_length: int = Field(default=1000, alias="CRM_OPERATOR_REPLY_MAX_LENGTH")
    crm_operator_reply_block_stopped: bool = Field(default=True, alias="CRM_OPERATOR_REPLY_BLOCK_STOPPED")
    crm_inbox_auto_refresh_seconds: int = Field(default=15, alias="CRM_INBOX_AUTO_REFRESH_SECONDS")
    crm_sla_due_soon_minutes: int = Field(default=5, alias="CRM_SLA_DUE_SOON_MINUTES")
    crm_sla_overdue_minutes: int = Field(default=15, alias="CRM_SLA_OVERDUE_MINUTES")
    crm_sla_critical_minutes: int = Field(default=30, alias="CRM_SLA_CRITICAL_MINUTES")
    crm_segments_enabled: bool = Field(default=True, alias="CRM_SEGMENTS_ENABLED")
    crm_enrichment_enabled: bool = Field(default=True, alias="CRM_ENRICHMENT_ENABLED")

    # Business hours (Time-Aware Intelligence Layer)
    timezone: str = Field(default="Asia/Tashkent", alias="BUSINESS_TIMEZONE")
    business_hours_start: int = Field(default=9, alias="BUSINESS_HOURS_START", ge=0, le=23)
    business_hours_end: int = Field(default=20, alias="BUSINESS_HOURS_END", ge=1, le=24)

    # Agent follow-up engine
    agent_followups_enabled: bool = Field(default=False, alias="AGENT_FOLLOWUPS_ENABLED")
    agent_catalog_followup_enabled: bool = Field(default=False, alias="AGENT_CATALOG_FOLLOWUP_ENABLED")
    agent_price_followup_enabled: bool = Field(default=False, alias="AGENT_PRICE_FOLLOWUP_ENABLED")
    agent_order_followup_enabled: bool = Field(default=False, alias="AGENT_ORDER_FOLLOWUP_ENABLED")
    agent_catalog_followup_delay_minutes: int = Field(
        default=10, alias="AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES", ge=1, le=1440,
    )
    agent_price_followup_delay_minutes: int = Field(
        default=10, alias="AGENT_PRICE_FOLLOWUP_DELAY_MINUTES", ge=1, le=1440,
    )
    agent_order_followup_delay_minutes: int = Field(
        default=10, alias="AGENT_ORDER_FOLLOWUP_DELAY_MINUTES", ge=1, le=1440,
    )
    agent_admin_escalation_enabled: bool = Field(
        default=False, alias="AGENT_ADMIN_ESCALATION_ENABLED",
    )
    agent_admin_escalation_after_followups: int = Field(
        default=2, alias="AGENT_ADMIN_ESCALATION_AFTER_FOLLOWUPS", ge=1, le=10,
    )
    agent_admin_escalation_cooldown_minutes: int = Field(
        default=60, alias="AGENT_ADMIN_ESCALATION_COOLDOWN_MINUTES", ge=5, le=1440,
    )
    agent_ai_composer_enabled: bool = Field(
        default=False, alias="AGENT_AI_COMPOSER_ENABLED",
    )
    agent_ai_composer_model: str = Field(
        default="gpt-4o-mini", alias="AGENT_AI_COMPOSER_MODEL",
    )
    agent_ai_composer_timeout_seconds: int = Field(
        default=8, alias="AGENT_AI_COMPOSER_TIMEOUT_SECONDS", ge=3, le=30,
    )
    agent_ai_composer_max_tokens: int = Field(
        default=180, alias="AGENT_AI_COMPOSER_MAX_TOKENS", ge=50, le=500,
    )
    agent_decision_engine_enabled: bool = Field(
        default=False, alias="AGENT_DECISION_ENGINE_ENABLED",
    )
    agent_decision_log_only: bool = Field(
        default=True, alias="AGENT_DECISION_LOG_ONLY",
    )
    agent_decision_min_confidence: int = Field(
        default=60, alias="AGENT_DECISION_MIN_CONFIDENCE", ge=0, le=100,
    )
    agent_lead_signal_enabled: bool = Field(
        default=False, alias="AGENT_LEAD_SIGNAL_ENABLED",
    )
    agent_lead_signal_min_confidence: int = Field(
        default=50, alias="AGENT_LEAD_SIGNAL_MIN_CONFIDENCE", ge=0, le=100,
    )
    agent_lead_scoring_enabled: bool = Field(
        default=False, alias="AGENT_LEAD_SCORING_ENABLED",
    )
    agent_dynamic_offer_enabled: bool = Field(
        default=False, alias="AGENT_DYNAMIC_OFFER_ENABLED",
    )
    agent_dynamic_offer_min_confidence: int = Field(
        default=60, alias="AGENT_DYNAMIC_OFFER_MIN_CONFIDENCE", ge=0, le=100,
    )
    agent_dynamic_offer_log_only: bool = Field(
        default=True, alias="AGENT_DYNAMIC_OFFER_LOG_ONLY",
    )
    agent_conversation_policy_enabled: bool = Field(
        default=False, alias="AGENT_CONVERSATION_POLICY_ENABLED",
    )
    agent_conversation_policy_log_only: bool = Field(
        default=True, alias="AGENT_CONVERSATION_POLICY_LOG_ONLY",
    )
    agent_conversation_policy_min_confidence: int = Field(
        default=60, alias="AGENT_CONVERSATION_POLICY_MIN_CONFIDENCE", ge=0, le=100,
    )
    agent_runtime_settings_enabled: bool = Field(
        default=False, alias="AGENT_RUNTIME_SETTINGS_ENABLED",
    )
    agent_runtime_settings_cache_ttl_seconds: int = Field(
        default=30, alias="AGENT_RUNTIME_SETTINGS_CACHE_TTL_SECONDS", ge=5, le=300,
    )
    agent_runtime_settings_fail_open_to_env: bool = Field(
        default=True, alias="AGENT_RUNTIME_SETTINGS_FAIL_OPEN_TO_ENV",
    )
    agent_settings_mutation_enabled: bool = Field(
        default=False, alias="AGENT_SETTINGS_MUTATION_ENABLED",
    )
    agent_settings_require_confirmation: bool = Field(
        default=True, alias="AGENT_SETTINGS_REQUIRE_CONFIRMATION",
    )
    agent_settings_allow_live_flags: bool = Field(
        default=False, alias="AGENT_SETTINGS_ALLOW_LIVE_FLAGS",
    )
    agent_execution_api_approval_enabled: bool = Field(
        default=False, alias="AGENT_EXECUTION_API_APPROVAL_ENABLED",
    )
    agent_execution_live_sender_enabled: bool = Field(
        default=False, alias="AGENT_EXECUTION_LIVE_SENDER_ENABLED",
    )
    agent_execution_live_sender_batch_limit: int = Field(
        default=10, alias="AGENT_EXECUTION_LIVE_SENDER_BATCH_LIMIT", ge=1, le=50,
    )
    agent_execution_live_sender_revalidate: bool = Field(
        default=True, alias="AGENT_EXECUTION_LIVE_SENDER_REVALIDATE",
    )
    agent_execution_live_sender_mark_failed_on_error: bool = Field(
        default=True, alias="AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR",
    )
    agent_execution_queue_enabled: bool = Field(
        default=False, alias="AGENT_EXECUTION_QUEUE_ENABLED",
    )
    agent_execution_approval_ttl_minutes: int = Field(
        default=30, alias="AGENT_EXECUTION_APPROVAL_TTL_MINUTES", ge=5, le=1440,
    )
    agent_execution_approval_admin_notify: bool = Field(
        default=False, alias="AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY",
    )
    agent_execution_auto_execute_approved: bool = Field(
        default=False, alias="AGENT_EXECUTION_AUTO_EXECUTE_APPROVED",
    )
    agent_execution_sandbox_enabled: bool = Field(
        default=False, alias="AGENT_EXECUTION_SANDBOX_ENABLED",
    )
    agent_execution_mode: str = Field(
        default="log_only", alias="AGENT_EXECUTION_MODE",
    )
    agent_execution_canary_user_ids: str = Field(
        default="", alias="AGENT_EXECUTION_CANARY_USER_IDS",
    )
    agent_execution_require_approval_user_dm: bool = Field(
        default=True, alias="AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM",
    )
    agent_execution_require_approval_admin_alert: bool = Field(
        default=False, alias="AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT",
    )
    agent_execution_max_daily_per_user: int = Field(
        default=3, alias="AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER", ge=1, le=50,
    )
    agent_execution_trace_enabled: bool = Field(
        default=True, alias="AGENT_EXECUTION_TRACE_ENABLED",
    )
    agent_text_normalization_enabled: bool = Field(
        default=True, alias="AGENT_TEXT_NORMALIZATION_ENABLED",
    )
    agent_fuzzy_intent_enabled: bool = Field(
        default=True, alias="AGENT_FUZZY_INTENT_ENABLED",
    )
    agent_fuzzy_max_distance: int = Field(
        default=1, alias="AGENT_FUZZY_MAX_DISTANCE", ge=1, le=3,
    )
    agent_response_orchestrator_enabled: bool = Field(
        default=False, alias="AGENT_RESPONSE_ORCHESTRATOR_ENABLED",
    )
    agent_response_orchestrator_log_only: bool = Field(
        default=True, alias="AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY",
    )
    agent_response_orchestrator_min_confidence: int = Field(
        default=60, alias="AGENT_RESPONSE_ORCHESTRATOR_MIN_CONFIDENCE", ge=0, le=100,
    )
    agent_response_orchestrator_trace_enabled: bool = Field(
        default=True, alias="AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED",
    )


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
    cta: CTASettings = Field(default_factory=CTASettings)
    api: ApiSettings = Field(default_factory=ApiSettings)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce production-specific requirements."""
        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("DEBUG must be False in production")
            if not self.bot.webhook_url:
                raise ValueError("BOT_WEBHOOK_URL is required in production")
            if self.bot.webhook_url and not self.bot.webhook_secret:
                raise ValueError("BOT_WEBHOOK_SECRET is required when webhook is enabled in production")
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
