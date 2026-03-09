"""
infrastructure.cache.bot_registry_state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Redis-backed state persistence for BotRegistry.

Provides:
- State persistence: BotRuntimeState serialised to Redis hashes
- Ownership locks: per-bot mutex so only one instance manages each bot
- Instance heartbeat: liveness signal so dead instances can be reclaimed
- Recovery: list all known tenant states from Redis after restart

Design notes:
- aiogram Bot objects are NOT serialised (they must be re-created in-memory).
  Redis only stores metadata (status, bot_id, timestamps, errors).
- Ownership lock uses SET NX EX with a Lua-based release (same pattern as
  DistributedLock) to prevent two instances polling the same bot.
- Instance heartbeat is a simple key with TTL. If missing, the instance is
  dead and its bots are orphaned (available for reclaim).

Usage:
    from infrastructure.cache.bot_registry_state import BotRegistryRedisState

    redis_state = BotRegistryRedisState(instance_id="abc123")
    await redis_state.persist_state(state)
    recovered = await redis_state.load_state(tenant_id=1)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

# Lua script: release ownership only if we hold it (same pattern as scheduler lock).
_RELEASE_OWNER_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


def _dt_to_str(dt: datetime | None) -> str:
    """Serialise datetime to ISO string (or empty)."""
    return dt.isoformat() if dt else ""


def _str_to_dt(s: str) -> datetime | None:
    """Deserialise ISO string to datetime (or None)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


class BotRegistryRedisState:
    """Redis state layer for BotRegistry.

    Each instance of the application gets a unique ``instance_id``.
    The instance uses ownership locks to claim exclusive control of
    individual tenant bots.

    Args:
        instance_id: Unique identifier for this process (UUID hex).
    """

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id

    # ── Helpers ────────────────────────────────────────────────────────

    def _cache(self) -> Any:
        from infrastructure.cache.client import get_redis
        return get_redis()

    def _keys(self) -> type:
        from infrastructure.cache.keys import CacheKeys
        return CacheKeys

    def _ttl(self) -> type:
        from infrastructure.cache.keys import CacheTTL
        return CacheTTL

    # ── State persistence ─────────────────────────────────────────────

    async def persist_state(
        self,
        tenant_id: int,
        *,
        status: str,
        bot_id: int | None = None,
        tenant_name: str = "",
        last_started: datetime | None = None,
        last_health_check: datetime | None = None,
        last_error: str | None = None,
        last_error_at: datetime | None = None,
        error_count: int = 0,
        pause_reason: str | None = None,
    ) -> None:
        """Write bot state to a Redis hash."""
        cache = self._cache()
        keys = self._keys()
        ttl = self._ttl()

        key = keys.bot_registry_state(tenant_id)
        mapping = {
            "tenant_id": str(tenant_id),
            "status": status,
            "bot_id": str(bot_id) if bot_id else "",
            "tenant_name": tenant_name,
            "instance_id": self.instance_id,
            "last_started": _dt_to_str(last_started),
            "last_health_check": _dt_to_str(last_health_check),
            "last_error": last_error or "",
            "last_error_at": _dt_to_str(last_error_at),
            "error_count": str(error_count),
            "pause_reason": pause_reason or "",
        }
        await cache.hset(key, mapping)
        await cache.expire(key, ttl.BOT_REGISTRY_STATE)

        # Track tenant in the set of known tenants
        tenants_key = keys.bot_registry_tenants()
        await cache._redis.sadd(cache._key(tenants_key), str(tenant_id))

    async def load_state(self, tenant_id: int) -> dict[str, Any] | None:
        """Load bot state from Redis hash. Returns None if no state."""
        cache = self._cache()
        keys = self._keys()

        key = keys.bot_registry_state(tenant_id)
        data = await cache.hgetall(key)
        if not data:
            return None

        return {
            "tenant_id": int(data.get("tenant_id", tenant_id)),
            "status": data.get("status", ""),
            "bot_id": int(data["bot_id"]) if data.get("bot_id") else None,
            "tenant_name": data.get("tenant_name", ""),
            "instance_id": data.get("instance_id", ""),
            "last_started": _str_to_dt(data.get("last_started", "")),
            "last_health_check": _str_to_dt(data.get("last_health_check", "")),
            "last_error": data.get("last_error") or None,
            "last_error_at": _str_to_dt(data.get("last_error_at", "")),
            "error_count": int(data.get("error_count", 0)),
            "pause_reason": data.get("pause_reason") or None,
        }

    async def remove_state(self, tenant_id: int) -> None:
        """Remove bot state from Redis."""
        cache = self._cache()
        keys = self._keys()

        await cache.delete(keys.bot_registry_state(tenant_id))
        tenants_key = keys.bot_registry_tenants()
        await cache._redis.srem(cache._key(tenants_key), str(tenant_id))

    async def list_known_tenants(self) -> set[int]:
        """Return set of tenant IDs that have state in Redis."""
        cache = self._cache()
        keys = self._keys()

        tenants_key = keys.bot_registry_tenants()
        members = await cache._redis.smembers(cache._key(tenants_key))
        result: set[int] = set()
        for m in members:
            try:
                result.add(int(m))
            except (ValueError, TypeError):
                pass
        return result

    # ── Ownership lock ────────────────────────────────────────────────

    async def acquire_ownership(self, tenant_id: int) -> bool:
        """Try to claim exclusive ownership of a tenant's bot.

        Returns True if this instance now owns the bot, False if
        another live instance holds it.
        """
        cache = self._cache()
        keys = self._keys()
        ttl = self._ttl()

        key = keys.bot_registry_owner(tenant_id)
        acquired = await cache.set(
            key, self.instance_id,
            ttl=ttl.BOT_REGISTRY_OWNER, nx=True,
        )
        if acquired:
            return True

        # Check if current owner is still alive
        current_owner = await cache.get(key)
        if current_owner == self.instance_id:
            return True  # We already own it

        if current_owner:
            owner_alive = await self._is_instance_alive(current_owner)
            if not owner_alive:
                # Dead owner — force reclaim via Lua (atomic check-and-swap)
                reclaimed = await self._force_reclaim(tenant_id, current_owner)
                return reclaimed

        return False

    async def release_ownership(self, tenant_id: int) -> None:
        """Release ownership of a tenant's bot (only if we hold it)."""
        cache = self._cache()
        keys = self._keys()

        prefixed_key = cache._key(keys.bot_registry_owner(tenant_id))
        try:
            await cache._redis.eval(
                _RELEASE_OWNER_LUA, 1, prefixed_key, self.instance_id,
            )
        except Exception:
            log.warning("bot_owner_release_failed", tenant_id=tenant_id)

    async def renew_ownership(self, tenant_id: int) -> bool:
        """Renew the ownership lock TTL. Returns False if we lost it."""
        cache = self._cache()
        keys = self._keys()
        ttl = self._ttl()

        key = keys.bot_registry_owner(tenant_id)
        current = await cache.get(key)
        if current != self.instance_id:
            return False
        await cache.expire(key, ttl.BOT_REGISTRY_OWNER)
        return True

    async def get_owner(self, tenant_id: int) -> str | None:
        """Return the instance_id that owns this bot, or None."""
        cache = self._cache()
        keys = self._keys()
        return await cache.get(keys.bot_registry_owner(tenant_id))

    async def _force_reclaim(self, tenant_id: int, dead_owner: str) -> bool:
        """Atomically replace dead owner with ourselves.

        Uses Lua: if current value == dead_owner, SET to our instance_id with TTL.
        """
        cache = self._cache()
        keys = self._keys()
        ttl = self._ttl()

        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            redis.call("SET", KEYS[1], ARGV[2], "EX", ARGV[3])
            return 1
        else
            return 0
        end
        """
        prefixed_key = cache._key(keys.bot_registry_owner(tenant_id))
        result = await cache._redis.eval(
            lua, 1, prefixed_key,
            dead_owner, self.instance_id, str(ttl.BOT_REGISTRY_OWNER),
        )
        reclaimed = bool(result)
        if reclaimed:
            log.info(
                "bot_ownership_reclaimed",
                tenant_id=tenant_id,
                dead_owner=dead_owner,
                new_owner=self.instance_id,
            )
        return reclaimed

    # ── Instance heartbeat ────────────────────────────────────────────

    async def send_heartbeat(self) -> None:
        """Update this instance's heartbeat key."""
        cache = self._cache()
        keys = self._keys()
        ttl = self._ttl()

        key = keys.bot_registry_heartbeat(self.instance_id)
        await cache.set(key, "1", ttl=ttl.BOT_REGISTRY_HEARTBEAT)

    async def _is_instance_alive(self, instance_id: str) -> bool:
        """Check if another instance is still sending heartbeats."""
        cache = self._cache()
        keys = self._keys()

        key = keys.bot_registry_heartbeat(instance_id)
        return await cache.exists(key) > 0

    # ── Recovery helpers ──────────────────────────────────────────────

    async def get_running_tenants(self) -> list[dict[str, Any]]:
        """Return states for all tenants that were RUNNING before crash.

        Used at startup to know which bots need to be re-created.
        """
        known = await self.list_known_tenants()
        running: list[dict[str, Any]] = []

        for tid in known:
            state = await self.load_state(tid)
            if state and state.get("status") in ("running", "starting"):
                running.append(state)

        return running

    async def get_orphaned_tenants(self) -> list[dict[str, Any]]:
        """Return tenants whose owner is dead (heartbeat expired).

        These bots were running on a crashed/stopped instance and
        need to be reclaimed by a live instance.
        """
        known = await self.list_known_tenants()
        orphaned: list[dict[str, Any]] = []

        for tid in known:
            state = await self.load_state(tid)
            if not state or state.get("status") not in ("running", "starting"):
                continue

            owner = await self.get_owner(tid)
            if owner is None:
                # No owner at all — orphaned
                orphaned.append(state)
            elif owner != self.instance_id:
                alive = await self._is_instance_alive(owner)
                if not alive:
                    orphaned.append(state)

        return orphaned
