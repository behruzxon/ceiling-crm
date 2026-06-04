"""Production fail-closed config validation.

validate_production_settings must require, in production, the secrets that the
runtime auth fail-closes on — otherwise a misconfigured prod deploy passes
config validation while the REST API (require_api_token) and web dashboard
(Basic Auth) reject every request:

  - API_INTERNAL_TOKEN  (api.internal_token)
  - WEB_DASHBOARD_USERNAME + WEB_DASHBOARD_PASSWORD (read from the environment)

Already-enforced rules (DEBUG off, BOT_WEBHOOK_URL/SECRET, SENTRY_DSN) must keep
working, and development must still run with none of these set.

Hermetic: every Settings is built with ``_env_file=None`` and explicit fields so
the real .env never leaks in; web creds are controlled via monkeypatch. No DB,
Redis, network, Telegram, or OpenAI.
"""

from __future__ import annotations

import pytest

from shared.config.settings import (
    ApiSettings,
    BotSettings,
    DatabaseSettings,
    OpenAISettings,
    SentrySettings,
    Settings,
)

_WEB_USER = "WEB_DASHBOARD_USERNAME"
_WEB_PASS = "WEB_DASHBOARD_PASSWORD"


def _bot(**overrides) -> BotSettings:
    base = dict(
        _env_file=None,
        token="123456:ABCDEF",
        admin_group_id=-1001234567890,
        webhook_url="https://example.com",
        webhook_secret="whsecret",
    )
    base.update(overrides)
    return BotSettings(**base)


def _make(**overrides) -> Settings:
    """Build a Settings instance with a fully-valid production baseline."""
    base = dict(
        _env_file=None,
        app_env="production",
        app_debug=False,
        app_secret_key="test-secret",
        bot=_bot(),
        db=DatabaseSettings(_env_file=None, password="pw"),
        openai=OpenAISettings(_env_file=None, api_key="sk-test"),
        sentry=SentrySettings(_env_file=None, dsn="https://sentry.example/1"),
        api=ApiSettings(_env_file=None, internal_token="api-token"),
    )
    base.update(overrides)
    return Settings(**base)


def _set_web_creds(monkeypatch, user: str | None = "admin", password: str | None = "secret"):
    for key, val in ((_WEB_USER, user), (_WEB_PASS, password)):
        if val is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, val)


# ── development still runs with no production secrets ─────────────────────────


class TestDevelopmentUnaffected:
    def test_dev_runs_without_any_production_secrets(self, monkeypatch):
        _set_web_creds(monkeypatch, None, None)  # no web creds
        s = _make(
            app_env="development",
            bot=_bot(webhook_url=None, webhook_secret=None),
            sentry=SentrySettings(_env_file=None, dsn=None),
            api=ApiSettings(_env_file=None, internal_token=None),
        )
        assert s.app_env == "development"


# ── production requires the API auth token ───────────────────────────────────


class TestProductionRequiresApiToken:
    def test_missing_api_token_fails(self, monkeypatch):
        _set_web_creds(monkeypatch)  # web creds present so we reach the api check
        with pytest.raises(ValueError, match="API_INTERNAL_TOKEN"):
            _make(api=ApiSettings(_env_file=None, internal_token=None))


# ── production requires web dashboard credentials ────────────────────────────


class TestProductionRequiresWebCreds:
    def test_missing_both_fails(self, monkeypatch):
        _set_web_creds(monkeypatch, None, None)
        with pytest.raises(ValueError, match="WEB_DASHBOARD"):
            _make()

    def test_missing_password_only_fails(self, monkeypatch):
        _set_web_creds(monkeypatch, "admin", None)
        with pytest.raises(ValueError, match="WEB_DASHBOARD"):
            _make()

    def test_missing_username_only_fails(self, monkeypatch):
        _set_web_creds(monkeypatch, None, "secret")
        with pytest.raises(ValueError, match="WEB_DASHBOARD"):
            _make()


# ── production with the minimal required settings passes ─────────────────────


class TestProductionMinimalValid:
    def test_full_production_passes(self, monkeypatch):
        _set_web_creds(monkeypatch)
        s = _make()
        assert s.app_env == "production"
        assert s.api.internal_token is not None


# ── existing production rules still enforced ─────────────────────────────────


class TestExistingProductionRulesPreserved:
    def test_debug_true_fails(self, monkeypatch):
        _set_web_creds(monkeypatch)
        with pytest.raises(ValueError, match="DEBUG"):
            _make(app_debug=True)

    def test_missing_webhook_url_fails(self, monkeypatch):
        _set_web_creds(monkeypatch)
        with pytest.raises(ValueError, match="BOT_WEBHOOK_URL"):
            _make(bot=_bot(webhook_url=None))

    def test_missing_webhook_secret_fails(self, monkeypatch):
        _set_web_creds(monkeypatch)
        with pytest.raises(ValueError, match="BOT_WEBHOOK_SECRET"):
            _make(bot=_bot(webhook_secret=None))

    def test_missing_sentry_dsn_fails(self, monkeypatch):
        _set_web_creds(monkeypatch)
        with pytest.raises(ValueError, match="SENTRY_DSN"):
            _make(sentry=SentrySettings(_env_file=None, dsn=None))
