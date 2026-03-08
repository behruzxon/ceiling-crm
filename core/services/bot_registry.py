"""
core.services.bot_registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Central registry for multi-bot runtime.

Manages Bot instances for all active tenants, provides lookups by
bot_id -> tenant_id, tracks per-bot runtime status, and supports
dynamic lifecycle operations (start/stop/restart/resync).

Usage:
    from core.services.bot_registry import get_bot_registry
    registry = get_bot_registry()
    await registry.load_from_db(session)
    bots = registry.all_bots()
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from shared.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)


# ── Status model ─────────────────────────────────────────────────────────


class BotStatus(str, Enum):
    """Runtime status of a tenant bot."""

    STARTING = "starting"   # getMe validation in progress
    RUNNING  = "running"    # validated and active
    FAILED   = "failed"     # token invalid, network error, or duplicate
    STOPPED  = "stopped"    # administratively stopped via command
    PAUSED   = "paused"     # tenant is_active=False in DB


@dataclass
class BotRuntimeState:
    """Mutable runtime state for a single tenant bot. In-memory only."""

    tenant_id: int
    tenant_name: str
    bot_id: int | None = None
    status: BotStatus = BotStatus.STARTING
    last_start_attempt: datetime | None = None
    last_started: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_health_check: datetime | None = None
    error_count: int = 0
    pause_reason: str | None = None  # "inactive" | "billing_expired" | "billing_suspended"


@dataclass(frozen=True)
class TenantBotConfig:
    """Immutable snapshot of a tenant's bot-related configuration."""

    tenant_id: int
    bot_token: str
    bot_username: str | None
    admin_group_id: int | None
    main_group_id: int | None
    business_type: str


# ── Helpers ──────────────────────────────────────────────────────────────


def _hash_token(token: str) -> str:
    """SHA-256 hash (truncated) for dedup index. Never stores raw tokens."""
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Registry ─────────────────────────────────────────────────────────────


class BotRegistry:
    """
    Manages aiogram Bot instances for all active tenants.

    In multi-bot mode the Dispatcher is shared; each tenant has its own Bot
    instance keyed by ``bot.id`` (Telegram user-id of the bot account).
    """

    def __init__(self) -> None:
        self._bots: dict[int, Bot] = {}                    # bot_id -> Bot
        self._tenant_map: dict[int, int] = {}               # bot_id -> tenant_id
        self._configs: dict[int, TenantBotConfig] = {}      # tenant_id -> config
        self._states: dict[int, BotRuntimeState] = {}       # tenant_id -> runtime state
        self._token_index: dict[str, int] = {}              # token_hash -> tenant_id

    # ── Loading ──────────────────────────────────────────────────────────

    async def load_from_db(self, session: AsyncSession) -> None:
        """Fetch tenants with bot tokens and create Bot instances.

        Loads both active and inactive tenants for visibility.
        Inactive tenants are marked PAUSED. Duplicate tokens are detected.
        """
        from infrastructure.database.models.tenant import TenantModel
        from sqlalchemy import select

        stmt = select(TenantModel).where(
            TenantModel.bot_token.isnot(None),
        )
        result = await session.execute(stmt)
        tenants = result.scalars().all()

        counts = {"total": 0, "running": 0, "failed": 0, "paused": 0, "duplicates": 0}

        for tenant in tenants:
            counts["total"] += 1

            # Skip inactive tenants — mark as PAUSED
            if not tenant.is_active:
                self._states[tenant.id] = BotRuntimeState(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    status=BotStatus.PAUSED,
                    pause_reason="inactive",
                )
                counts["paused"] += 1
                log.info("bot_paused_inactive", tenant_id=tenant.id, slug=tenant.slug)
                continue

            # Skip expired/suspended billing — mark as PAUSED
            _billing = getattr(tenant, "billing_status", None)
            if _billing in ("expired", "suspended"):
                self._states[tenant.id] = BotRuntimeState(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    status=BotStatus.PAUSED,
                    pause_reason=f"billing_{_billing}",
                )
                counts["paused"] += 1
                log.info(
                    "bot_paused_billing",
                    tenant_id=tenant.id,
                    slug=tenant.slug,
                    billing_status=_billing,
                )
                continue

            # Skip empty tokens
            if not tenant.bot_token or not tenant.bot_token.strip():
                log.warning("bot_empty_token", tenant_id=tenant.id, slug=tenant.slug)
                continue

            # Duplicate token detection
            token_hash = _hash_token(tenant.bot_token)
            existing_tid = self._token_index.get(token_hash)
            if existing_tid is not None and existing_tid != tenant.id:
                self._states[tenant.id] = BotRuntimeState(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    status=BotStatus.FAILED,
                    last_error=f"duplicate_token (same as tenant {existing_tid})",
                    last_error_at=_now(),
                    error_count=1,
                )
                counts["duplicates"] += 1
                counts["failed"] += 1
                log.warning(
                    "bot_duplicate_token",
                    tenant_id=tenant.id,
                    duplicate_of=existing_tid,
                )
                continue

            # Register the bot
            await self._register_tenant(tenant)
            state = self._states.get(tenant.id)
            if state and state.status == BotStatus.RUNNING:
                counts["running"] += 1
            else:
                counts["failed"] += 1

        log.info("bot_registry_loaded", **counts)

    async def _register_tenant(self, tenant: object) -> None:
        """Create a Bot instance for a single tenant row."""
        tid = getattr(tenant, "id", 0)
        tname = getattr(tenant, "name", "?")
        token = getattr(tenant, "bot_token", "")

        state = self._states.get(tid) or BotRuntimeState(
            tenant_id=tid,
            tenant_name=tname,
        )
        state.status = BotStatus.STARTING
        state.last_start_attempt = _now()
        self._states[tid] = state

        try:
            bot = Bot(
                token=token,
                default=DefaultBotProperties(parse_mode="HTML"),
            )
            bot_info = await bot.get_me()
            bot_id = bot_info.id

            config = TenantBotConfig(
                tenant_id=tid,
                bot_token=token,
                bot_username=bot_info.username,
                admin_group_id=getattr(tenant, "admin_group_id", None),
                main_group_id=getattr(tenant, "main_group_id", None),
                business_type=getattr(tenant, "business_type", "other"),
            )

            self._bots[bot_id] = bot
            self._tenant_map[bot_id] = tid
            self._configs[tid] = config
            self._token_index[_hash_token(token)] = tid

            state.bot_id = bot_id
            state.status = BotStatus.RUNNING
            state.last_started = _now()
            state.last_health_check = _now()
            state.error_count = 0
            state.last_error = None

            log.info(
                "bot_registered",
                tenant_id=tid,
                bot_id=bot_id,
                bot_username=bot_info.username,
            )
        except Exception as exc:
            state.status = BotStatus.FAILED
            state.last_error = str(exc)[:200]
            state.last_error_at = _now()
            state.error_count += 1

            log.exception(
                "bot_registration_failed",
                tenant_id=tid,
                slug=getattr(tenant, "slug", "?"),
            )

    # ── Lookups ──────────────────────────────────────────────────────────

    def get_bot(self, bot_id: int) -> Bot | None:
        return self._bots.get(bot_id)

    def get_tenant_id(self, bot_id: int) -> int | None:
        return self._tenant_map.get(bot_id)

    def get_tenant_config(self, tenant_id: int) -> TenantBotConfig | None:
        return self._configs.get(tenant_id)

    def get_config_by_bot_id(self, bot_id: int) -> TenantBotConfig | None:
        tenant_id = self._tenant_map.get(bot_id)
        if tenant_id is None:
            return None
        return self._configs.get(tenant_id)

    def all_bots(self) -> list[Bot]:
        return list(self._bots.values())

    @property
    def bot_count(self) -> int:
        return len(self._bots)

    # ── Status ───────────────────────────────────────────────────────────

    def get_bot_state(self, tenant_id: int) -> BotRuntimeState | None:
        return self._states.get(tenant_id)

    def list_status(self) -> list[dict[str, Any]]:
        """Return status summary for each tracked tenant bot."""
        result = []
        for tenant_id, state in self._states.items():
            config = self._configs.get(tenant_id)
            result.append({
                "tenant_id": tenant_id,
                "tenant_name": state.tenant_name,
                "bot_id": state.bot_id,
                "bot_username": config.bot_username if config else None,
                "status": state.status.value,
                "last_started": state.last_started,
                "last_error": state.last_error,
                "last_error_at": state.last_error_at,
                "error_count": state.error_count,
            })
        return result

    # ── Lifecycle operations ─────────────────────────────────────────────

    async def stop_bot(self, tenant_id: int) -> bool:
        """Remove a bot from the active set and mark it STOPPED.

        In polling mode the bot continues receiving updates until process
        restart, but TenantContextMiddleware will find no config and the
        updates will be silently dropped.
        """
        state = self._states.get(tenant_id)
        if state is None:
            return False

        # Remove from active collections
        if state.bot_id and state.bot_id in self._bots:
            bot = self._bots.pop(state.bot_id)
            self._tenant_map.pop(state.bot_id, None)
            try:
                await bot.session.close()
            except Exception:
                log.exception("bot_session_close_error", bot_id=state.bot_id)

        # Remove config and token index entry
        config = self._configs.pop(tenant_id, None)
        if config:
            token_hash = _hash_token(config.bot_token)
            if self._token_index.get(token_hash) == tenant_id:
                self._token_index.pop(token_hash, None)

        state.status = BotStatus.STOPPED
        log.info("bot_stopped", tenant_id=tenant_id, bot_id=state.bot_id)
        return True

    async def start_bot(self, tenant_id: int, session: AsyncSession) -> BotStatus:
        """Attempt to start (or restart) a single tenant bot.

        Fetches the tenant from DB, validates token, registers if valid.
        """
        from infrastructure.database.models.tenant import TenantModel

        tenant = await session.get(TenantModel, tenant_id)
        if tenant is None:
            return BotStatus.FAILED

        if not tenant.is_active:
            state = self._states.get(tenant_id) or BotRuntimeState(
                tenant_id=tenant_id, tenant_name=tenant.name,
            )
            state.status = BotStatus.PAUSED
            state.pause_reason = "inactive"
            state.tenant_name = tenant.name
            self._states[tenant_id] = state
            return BotStatus.PAUSED

        _billing = getattr(tenant, "billing_status", None)
        if _billing in ("expired", "suspended"):
            state = self._states.get(tenant_id) or BotRuntimeState(
                tenant_id=tenant_id, tenant_name=tenant.name,
            )
            state.status = BotStatus.PAUSED
            state.pause_reason = f"billing_{_billing}"
            state.tenant_name = tenant.name
            self._states[tenant_id] = state
            return BotStatus.PAUSED

        if not tenant.bot_token or not tenant.bot_token.strip():
            return BotStatus.FAILED

        # Duplicate check
        token_hash = _hash_token(tenant.bot_token)
        existing_tid = self._token_index.get(token_hash)
        if existing_tid is not None and existing_tid != tenant_id:
            state = self._states.get(tenant_id) or BotRuntimeState(
                tenant_id=tenant_id, tenant_name=tenant.name,
            )
            state.status = BotStatus.FAILED
            state.last_error = f"duplicate_token (same as tenant {existing_tid})"
            state.last_error_at = _now()
            self._states[tenant_id] = state
            return BotStatus.FAILED

        # Stop existing instance if any
        await self.stop_bot(tenant_id)

        # Register fresh
        await self._register_tenant(tenant)
        state = self._states.get(tenant_id)
        return state.status if state else BotStatus.FAILED

    async def restart_bot(self, tenant_id: int, session: AsyncSession) -> BotStatus:
        """Stop then start a bot. Returns resulting status."""
        await self.stop_bot(tenant_id)
        return await self.start_bot(tenant_id, session)

    async def resync_from_db(self, session: AsyncSession) -> dict[str, int]:
        """Reload all tenant configs from DB.

        - New active tenants get started.
        - Deactivated tenants get paused.
        - Changed tokens get restarted.
        - Unchanged running bots are left alone.
        """
        from infrastructure.database.models.tenant import TenantModel
        from sqlalchemy import select

        stmt = select(TenantModel).where(TenantModel.bot_token.isnot(None))
        result = await session.execute(stmt)
        db_tenants = {t.id: t for t in result.scalars().all()}

        added, removed, restarted, unchanged = 0, 0, 0, 0

        # 1. Remove/pause bots no longer active in DB
        for tid in list(self._states.keys()):
            db_t = db_tenants.get(tid)
            if db_t is None:
                # Tenant removed from DB or token cleared
                await self.stop_bot(tid)
                removed += 1
            elif not db_t.is_active or getattr(db_t, "billing_status", None) in ("expired", "suspended"):
                await self.stop_bot(tid)
                state = self._states.get(tid)
                if state:
                    state.status = BotStatus.PAUSED
                    _bs = getattr(db_t, "billing_status", None)
                    state.pause_reason = f"billing_{_bs}" if _bs in ("expired", "suspended") else "inactive"
                removed += 1

        # 2. Add/update bots from DB
        for tid, tenant in db_tenants.items():
            _billing = getattr(tenant, "billing_status", None)
            if not tenant.is_active or _billing in ("expired", "suspended"):
                if tid not in self._states:
                    _reason = f"billing_{_billing}" if _billing in ("expired", "suspended") else "inactive"
                    self._states[tid] = BotRuntimeState(
                        tenant_id=tid, tenant_name=tenant.name,
                        status=BotStatus.PAUSED, pause_reason=_reason,
                    )
                continue

            if not tenant.bot_token or not tenant.bot_token.strip():
                continue

            existing_config = self._configs.get(tid)

            if existing_config is None:
                # New tenant — check for duplicate before starting
                token_hash = _hash_token(tenant.bot_token)
                dup_tid = self._token_index.get(token_hash)
                if dup_tid is not None and dup_tid != tid:
                    self._states[tid] = BotRuntimeState(
                        tenant_id=tid, tenant_name=tenant.name,
                        status=BotStatus.FAILED,
                        last_error=f"duplicate_token (same as tenant {dup_tid})",
                        last_error_at=_now(), error_count=1,
                    )
                    log.warning("bot_duplicate_token_resync", tenant_id=tid, duplicate_of=dup_tid)
                    added += 1  # counted as attempted add
                    continue
                await self._register_tenant(tenant)
                added += 1
            elif existing_config.bot_token != tenant.bot_token:
                # Token changed — restart
                await self.stop_bot(tid)
                await self._register_tenant(tenant)
                restarted += 1
            else:
                unchanged += 1

        summary = {
            "added": added, "removed": removed,
            "restarted": restarted, "unchanged": unchanged,
        }
        log.info("registry_resynced", **summary)
        return summary

    async def shutdown_all(self) -> None:
        """Close all Bot sessions gracefully."""
        for state in self._states.values():
            state.status = BotStatus.STOPPED

        for bot_id, bot in self._bots.items():
            try:
                await bot.session.close()
            except Exception:
                log.exception("bot_session_close_error", bot_id=bot_id)

        self._bots.clear()
        self._tenant_map.clear()
        self._configs.clear()
        self._token_index.clear()
        log.info("bot_registry_shutdown")


# ── Module-level singleton ───────────────────────────────────────────────

_registry: BotRegistry | None = None


def get_bot_registry() -> BotRegistry:
    """Return (or create) the module-level BotRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = BotRegistry()
    return _registry
