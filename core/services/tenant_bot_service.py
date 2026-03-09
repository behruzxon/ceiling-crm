"""
core.services.tenant_bot_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestration service for tenant bot lifecycle: validate, connect,
disconnect, reconnect, webhook management, health checks.

Usage::

    factory = get_session_factory()
    async with factory() as session:
        svc = TenantBotService(session)
        info = await svc.validate_token("123456:ABC...")
        status = await svc.connect_bot(tenant_id=42, token="123456:ABC...")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from core.security.token_encryption import encrypt_token
from core.services.bot_registry import BotStatus, get_bot_registry
from shared.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)


# ── Result dataclasses ───────────────────────────────────────────────────


@dataclass(frozen=True)
class BotInfo:
    """Result of :meth:`validate_token`."""

    bot_id: int
    username: str | None
    first_name: str


@dataclass(frozen=True)
class BotStatusInfo:
    """Combined status from DB + BotRegistry for display."""

    tenant_id: int
    bot_username: str | None
    bot_id: int | None
    status: str  # BotStatus.value
    webhook_url: str | None
    webhook_set: bool
    last_health_check: datetime | None
    last_error: str | None
    uptime_since: datetime | None


# ── Helpers ──────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mask_token(token: str) -> str:
    """Show only first 4 and last 4 chars of a bot token."""
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


# ── Service ──────────────────────────────────────────────────────────────


class TenantBotService:
    """Tenant bot lifecycle orchestration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Token validation ─────────────────────────────────────────────────

    async def validate_token(self, token: str) -> BotInfo:
        """Create a temporary Bot, call ``getMe()``, return :class:`BotInfo`.

        Raises :class:`ValueError` on invalid/revoked token.
        Raises :class:`ConnectionError` on network failure.
        """
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            me = await bot.get_me()
            return BotInfo(
                bot_id=me.id,
                username=me.username,
                first_name=me.first_name,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "unauthorized" in err_str or "not found" in err_str:
                raise ValueError("Token yaroqsiz yoki bekor qilingan") from exc
            raise ConnectionError(
                f"Telegram API bilan bog'lanib bo'lmadi: {exc}"
            ) from exc
        finally:
            await bot.session.close()

    # ── Connect ──────────────────────────────────────────────────────────

    async def connect_bot(self, tenant_id: int, token: str) -> BotStatusInfo:
        """Validate token -> save to DB -> register in BotRegistry -> set webhook.

        Returns combined status after connection.
        """
        from infrastructure.database.models.tenant import TenantModel

        # 1. Validate
        bot_info = await self.validate_token(token)
        log.info(
            "bot_token_validated",
            tenant_id=tenant_id,
            bot_username=bot_info.username,
        )

        # 2. Save to DB
        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} topilmadi")

        tenant.bot_token = encrypt_token(token)
        tenant.bot_username = bot_info.username
        await self._session.flush()

        # 3. Register in BotRegistry
        registry = get_bot_registry()
        status = await registry.start_bot(tenant_id, self._session)
        log.info(
            "bot_connected",
            tenant_id=tenant_id,
            bot_username=bot_info.username,
            registry_status=status.value,
        )

        # 4. Set webhook if in webhook mode
        from shared.config import get_settings

        settings = get_settings()
        if settings.bot.webhook_url and status == BotStatus.RUNNING:
            try:
                await self._set_webhook_internal(tenant, registry)
            except Exception:
                log.warning(
                    "bot_webhook_set_failed",
                    tenant_id=tenant_id,
                )

        return self._build_status(tenant, registry)

    # ── Disconnect ───────────────────────────────────────────────────────

    async def disconnect_bot(self, tenant_id: int) -> bool:
        """Remove webhook -> stop in registry -> clear token fields in DB.

        Returns True if successfully disconnected.
        """
        from infrastructure.database.models.tenant import TenantModel

        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            return False

        registry = get_bot_registry()

        # 1. Remove webhook
        if tenant.webhook_set:
            await self._remove_webhook_internal(tenant, registry)

        # 2. Stop in registry
        await registry.stop_bot(tenant_id)

        # 3. Clear DB fields
        tenant.bot_token = None
        tenant.bot_username = None
        tenant.webhook_url = None
        tenant.webhook_set = False
        tenant.last_health_check = None
        await self._session.flush()

        log.info("bot_disconnected", tenant_id=tenant_id)
        return True

    # ── Reconnect ────────────────────────────────────────────────────────

    async def reconnect_bot(
        self, tenant_id: int, new_token: str,
    ) -> BotStatusInfo:
        """Validate new token first, then disconnect old and connect new.

        If new token validation fails, old state is preserved.
        """
        # Validate new token before touching old state
        new_info = await self.validate_token(new_token)
        log.info(
            "bot_reconnect_new_validated",
            tenant_id=tenant_id,
            new_username=new_info.username,
        )

        # Disconnect old
        await self.disconnect_bot(tenant_id)

        # Connect new
        return await self.connect_bot(tenant_id, new_token)

    # ── Webhook management ───────────────────────────────────────────────

    async def set_webhook(self, tenant_id: int) -> bool:
        """Call ``bot.set_webhook()`` with tenant-specific URL, update DB."""
        from infrastructure.database.models.tenant import TenantModel

        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            return False

        registry = get_bot_registry()
        return await self._set_webhook_internal(tenant, registry)

    async def remove_webhook(self, tenant_id: int) -> bool:
        """Call ``bot.delete_webhook()``, update DB."""
        from infrastructure.database.models.tenant import TenantModel

        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            return False

        registry = get_bot_registry()
        return await self._remove_webhook_internal(tenant, registry)

    async def _set_webhook_internal(self, tenant: object, registry: object) -> bool:
        from shared.config import get_settings

        settings = get_settings()
        state = registry.get_bot_state(tenant.id)
        if state is None or state.bot_id is None:
            return False

        bot = registry.get_bot(state.bot_id)
        if bot is None:
            return False

        url = f"{settings.bot.webhook_url}/webhook/{state.bot_id}"
        secret = settings.bot.webhook_secret.get_secret_value()

        await bot.set_webhook(url=url, secret_token=secret)
        tenant.webhook_url = url
        tenant.webhook_set = True
        await self._session.flush()

        log.info(
            "bot_webhook_set",
            tenant_id=tenant.id,
            bot_id=state.bot_id,
        )
        return True

    async def _remove_webhook_internal(self, tenant: object, registry: object) -> bool:
        state = registry.get_bot_state(tenant.id)
        if state is not None and state.bot_id is not None:
            bot = registry.get_bot(state.bot_id)
            if bot is not None:
                try:
                    await bot.delete_webhook()
                except Exception:
                    log.warning(
                        "bot_webhook_delete_failed",
                        tenant_id=tenant.id,
                    )

        tenant.webhook_url = None
        tenant.webhook_set = False
        await self._session.flush()

        log.info("bot_webhook_removed", tenant_id=tenant.id)
        return True

    # ── Health check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> BotStatusInfo | None:
        """Call ``getMe()`` on the tenant's bot, update last_health_check."""
        from infrastructure.database.models.tenant import TenantModel

        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            return None

        registry = get_bot_registry()
        state = registry.get_bot_state(tenant_id)
        if state is None or state.bot_id is None:
            return self._build_status(tenant, registry)

        bot = registry.get_bot(state.bot_id)
        if bot is None:
            return self._build_status(tenant, registry)

        now = _now()
        try:
            await bot.get_me()
            state.last_health_check = now
            tenant.last_health_check = now
            await self._session.flush()
        except Exception as exc:
            state.last_error = str(exc)[:200]
            state.last_error_at = now
            state.error_count += 1
            log.warning(
                "bot_health_check_failed",
                tenant_id=tenant_id,
                error=str(exc)[:100],
            )

        return self._build_status(tenant, registry)

    # ── Status ───────────────────────────────────────────────────────────

    async def get_bot_status(self, tenant_id: int) -> BotStatusInfo | None:
        """Return combined DB + registry status. No API calls."""
        from infrastructure.database.models.tenant import TenantModel

        tenant = await self._session.get(TenantModel, tenant_id)
        if tenant is None:
            return None

        registry = get_bot_registry()
        return self._build_status(tenant, registry)

    def _build_status(self, tenant: object, registry: object) -> BotStatusInfo:
        state = registry.get_bot_state(tenant.id)

        if state is not None:
            status = state.status.value
            bot_id = state.bot_id
            last_error = state.last_error
            uptime = state.last_started
        elif tenant.bot_token:
            status = "not_registered"
            bot_id = None
            last_error = None
            uptime = None
        else:
            status = "disconnected"
            bot_id = None
            last_error = None
            uptime = None

        return BotStatusInfo(
            tenant_id=tenant.id,
            bot_username=tenant.bot_username,
            bot_id=bot_id,
            status=status,
            webhook_url=tenant.webhook_url,
            webhook_set=tenant.webhook_set,
            last_health_check=tenant.last_health_check,
            last_error=last_error,
            uptime_since=uptime,
        )
