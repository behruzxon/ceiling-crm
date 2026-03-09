"""Tests for CORS configuration in shared/config/settings.py."""
from __future__ import annotations

import pytest


class TestCorsOriginsDefault:
    def test_default_cors_origins(self) -> None:
        """Default cors_origins must not contain '*' and include localhost origins."""
        from shared.config import Settings

        s = Settings()
        assert "*" not in s.cors_origins
        assert "http://localhost:3000" in s.cors_origins
        assert "http://localhost:8000" in s.cors_origins

    def test_cors_origins_env_json_array(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WEB_CORS_ORIGINS env var as JSON array is parsed correctly."""
        monkeypatch.setenv("WEB_CORS_ORIGINS", '["https://example.com"]')
        from shared.config import Settings

        s = Settings()
        assert s.cors_origins == ["https://example.com"]

    def test_cors_origins_env_multiple(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WEB_CORS_ORIGINS env var with multiple origins is parsed as a list."""
        monkeypatch.setenv("WEB_CORS_ORIGINS", '["https://a.com","https://b.com"]')
        from shared.config import Settings

        s = Settings()
        assert "https://a.com" in s.cors_origins
        assert "https://b.com" in s.cors_origins


class TestCorsProductionGuard:
    def _production_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set the minimum env vars required to construct a production Settings."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("APP_SECRET_KEY", "a" * 32)
        monkeypatch.setenv("BOT_TOKEN", "123456789:AAFakeBotTokenForTestingPurposesXXX")
        monkeypatch.setenv("BOT_WEBHOOK_URL", "https://example.com/webhook")
        monkeypatch.setenv("BOT_WEBHOOK_SECRET", "b" * 32)
        monkeypatch.setenv("BOT_ADMIN_GROUP_ID", "-100123456")
        monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.io/1")
        monkeypatch.setenv("POSTGRES_PASSWORD", "c" * 16)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key-that-is-long-enough")
        monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEY", "d" * 32)

    def test_wildcard_raises_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production env must reject cors_origins containing '*'."""
        self._production_env(monkeypatch)
        monkeypatch.setenv("WEB_CORS_ORIGINS", '["*"]')

        from pydantic import ValidationError
        from shared.config import Settings

        with pytest.raises((ValueError, ValidationError), match="WEB_CORS_ORIGINS"):
            Settings()

    def test_explicit_origin_ok_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production env accepts explicit non-wildcard origins."""
        self._production_env(monkeypatch)
        monkeypatch.setenv("WEB_CORS_ORIGINS", '["https://myapp.com"]')

        from shared.config import Settings

        s = Settings()  # should not raise
        assert "https://myapp.com" in s.cors_origins
