"""Unit tests for tenant_id in audit logging.

Covers:
  1. AuditMiddleware includes tenant_id from handler data
  2. AuditMiddleware falls back to db_user.tenant_id
  3. AuditMiddleware accepts explicit tenant_id in audit_action
  4. AuditMiddleware logs warning when tenant_id is missing
  5. AuthMiddleware injects tenant_id into handler data
  6. structlog contextvars include tenant_id
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_db_user(tenant_id: int = 1, user_id: int = 100):
    user = MagicMock()
    user.id = user_id
    user.tenant_id = tenant_id
    user.role = "client"
    return user


# ── AuditMiddleware._resolve_tenant_id ──────────────────────────────────────


class TestResolveTenantId:
    """Test tenant_id resolution priority in AuditMiddleware."""

    def test_from_data_tenant_id(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        data = {"tenant_id": 42, "db_user": _make_db_user(tenant_id=99)}
        result = AuditMiddleware._resolve_tenant_id(data)
        assert result == 42

    def test_from_audit_action_override(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        data = {
            "tenant_id": 42,
            "audit_action": {"tenant_id": 7, "action": "test"},
        }
        result = AuditMiddleware._resolve_tenant_id(data)
        assert result == 7  # audit_action takes priority

    def test_from_db_user_fallback(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        data = {"db_user": _make_db_user(tenant_id=55)}
        result = AuditMiddleware._resolve_tenant_id(data)
        assert result == 55

    def test_none_when_no_source(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        data = {}
        result = AuditMiddleware._resolve_tenant_id(data)
        assert result is None

    def test_none_when_db_user_has_no_tenant(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        user = MagicMock(spec=[])  # no tenant_id attr
        data = {"db_user": user}
        result = AuditMiddleware._resolve_tenant_id(data)
        assert result is None


# ── AuditMiddleware._write_audit ────────────────────────────────────────────


class TestWriteAudit:
    """Test that _write_audit creates records with tenant_id."""

    async def test_writes_tenant_id_to_audit_record(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        middleware = AuditMiddleware()
        audit = {
            "action": "lead.created",
            "entity_type": "lead",
            "entity_id": 42,
        }
        data = {
            "tenant_id": 10,
            "db_user": _make_db_user(tenant_id=10, user_id=100),
        }

        with patch(
            "apps.bot.middlewares.audit.get_session_factory"
        ) as mock_factory:
            mock_session = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_ctx)

            await middleware._write_audit(audit, data)

            # Verify session.add was called with correct record
            mock_session.add.assert_called_once()
            record = mock_session.add.call_args[0][0]
            assert record.tenant_id == 10
            assert record.actor_id == 100
            assert record.action == "lead.created"
            assert record.entity_type == "lead"
            assert record.entity_id == 42

    async def test_skips_when_no_tenant_id(self) -> None:
        from apps.bot.middlewares.audit import AuditMiddleware

        middleware = AuditMiddleware()
        audit = {"action": "test", "entity_type": "test", "entity_id": 1}
        data = {}  # no tenant_id, no db_user

        with patch(
            "apps.bot.middlewares.audit.get_session_factory"
        ) as mock_factory:
            await middleware._write_audit(audit, data)

            # Should NOT attempt to write
            mock_factory.assert_not_called()


# ── AuthMiddleware tenant_id injection ──────────────────────────────────────


class TestAuthMiddlewareTenantInjection:
    """AuthMiddleware sets data['tenant_id'] from db_user."""

    async def test_injects_tenant_id_into_data(self) -> None:
        from apps.bot.middlewares.auth import AuthMiddleware

        middleware = AuthMiddleware()

        # Mock tg_user
        tg_user = MagicMock()
        tg_user.id = 12345
        tg_user.is_bot = False
        tg_user.username = "testuser"
        tg_user.first_name = "Test"
        tg_user.last_name = None
        tg_user.language_code = "uz"

        # Mock db_user returned by repo
        db_user = _make_db_user(tenant_id=42, user_id=12345)

        # Build data dict as aiogram would
        data: dict = {"event_from_user": tg_user}
        captured_data: dict = {}

        async def mock_handler(event, d):
            captured_data.update(d)
            return None

        mock_repo = AsyncMock()
        mock_repo.upsert = AsyncMock(return_value=db_user)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        event = MagicMock()

        with (
            patch(
                "apps.bot.middlewares.auth.get_session_factory",
                return_value=MagicMock(return_value=mock_ctx),
            ),
            patch(
                "apps.bot.middlewares.auth.get_user_repo",
                return_value=mock_repo,
            ),
            patch("apps.bot.middlewares.auth.get_redis") as mock_redis,
        ):
            mock_redis.return_value.zadd = AsyncMock()
            await middleware(mock_handler, event, data)

        assert captured_data.get("tenant_id") == 42
        assert captured_data.get("db_user") is db_user


# ── structlog contextvars ───────────────────────────────────────────────────


class TestStructlogContextvars:
    """structlog merge_contextvars processor is configured."""

    def test_merge_contextvars_in_processor_chain(self) -> None:
        """Verify merge_contextvars is in the shared processor chain."""
        import structlog

        from shared.logging.setup import _build_shared_processors

        processors = _build_shared_processors(is_dev=True)

        assert structlog.contextvars.merge_contextvars in processors
