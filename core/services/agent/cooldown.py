"""
core.services.agent.cooldown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralised cooldown / dedup manager for the AI agent layer.

Current CRM code scatters 15+ independent Redis NX checks across handlers
and scheduled jobs (``closer:last:{uid}``, ``autosell:esc:{lid}``,
``conv:alert:{lid}``, etc.).  This module provides a **single, uniform**
cooldown mechanism that future agent rules will use instead.

Phase 1C — additive only.  No existing NX checks are removed; no handlers
are modified.  The manager is ready to be consumed once the rule-chain
engine is wired (Phase 1D+).

Import constraints
------------------
  - May import from ``infrastructure/`` (cache client, keys)
  - Must NOT import from ``apps/``

Usage (future)::

    from core.services.agent.cooldown import AgentCooldownManager, ActionType

    mgr = AgentCooldownManager()
    if await mgr.can_act(user_id, ActionType.ATTEMPT_CLOSE, cooldown_seconds=600):
        # … execute close CTA …
        await mgr.mark_acted(user_id, ActionType.ATTEMPT_CLOSE, cooldown_seconds=600)
"""

from __future__ import annotations

from enum import Enum

from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys
from shared.logging import get_logger

log = get_logger(__name__)

__all__ = ["ActionType", "AgentCooldownManager"]


# ── Action vocabulary ─────────────────────────────────────────────────────────


class ActionType(str, Enum):
    """Actions the agent can take.

    Each value maps to an existing branch in the CRM pipeline.
    Only actions that are *currently performed* by the codebase are listed;
    speculative future actions are deferred.
    """

    REPLY = "reply"
    """Send a text message to the user (auto-reply, negotiation, follow-up)."""

    ADMIN_ALERT = "admin_alert"
    """Send an alert / lead card to the admin group."""

    ATTEMPT_CLOSE = "attempt_close"
    """Send a closing CTA to the user (measurement booking, call offer)."""

    ESCALATE = "escalate"
    """Escalate to a human manager (alert + suggested action)."""

    SCHEDULE_FOLLOWUP = "schedule_followup"
    """Schedule a delayed follow-up reminder."""

    CATALOG_FOLLOWUP = "catalog_followup"
    """Send a catalog-inactivity nudge to the user."""

    NOOP = "noop"
    """Explicit decision to take no action."""


# ── Cooldown manager ──────────────────────────────────────────────────────────


class AgentCooldownManager:
    """Centralised per-user, per-action cooldown gate.

    Backed by Redis NX (set-if-not-exists) — the same primitive currently
    used by ``sales_closer``, ``auto_sales_escalation``, ``conv_intel``
    and others, but with a uniform key namespace:
    ``agent:cd:{user_id}:{action_type}``.

    Thread/coroutine safety is guaranteed by Redis atomicity of SET NX.
    """

    async def can_act(
        self,
        user_id: int,
        action_type: ActionType,
        *,
        cooldown_seconds: int,
    ) -> bool:
        """Return ``True`` if the cooldown for this user+action has expired.

        Does **not** acquire the lock — call :meth:`mark_acted` after
        the action succeeds to start a new cooldown window.

        Parameters
        ----------
        user_id:
            Telegram user ID.
        action_type:
            Which agent action to check.
        cooldown_seconds:
            How long the cooldown window lasts (in seconds).
        """
        if action_type is ActionType.NOOP:
            return True
        try:
            redis = get_redis()
            key = CacheKeys.agent_cooldown(user_id, action_type.value)
            return not await redis.exists(key)
        except Exception:
            log.warning(
                "agent_cd_check_error",
                user_id=user_id,
                action=action_type.value,
                exc_info=True,
            )
            # Fail-open: allow the action if Redis is unreachable.
            return True

    async def mark_acted(
        self,
        user_id: int,
        action_type: ActionType,
        *,
        cooldown_seconds: int,
    ) -> None:
        """Start a cooldown window for this user+action.

        Uses ``SET NX`` with the given TTL so the key auto-expires.

        Parameters
        ----------
        user_id:
            Telegram user ID.
        action_type:
            Which agent action was taken.
        cooldown_seconds:
            How long to suppress repeated actions (in seconds).
        """
        if action_type is ActionType.NOOP:
            return
        try:
            redis = get_redis()
            key = CacheKeys.agent_cooldown(user_id, action_type.value)
            await redis.set(key, "1", ttl=cooldown_seconds, nx=True)
        except Exception:
            log.warning(
                "agent_cd_mark_error",
                user_id=user_id,
                action=action_type.value,
                exc_info=True,
            )

    async def reset(
        self,
        user_id: int,
        action_type: ActionType,
    ) -> None:
        """Clear the cooldown for this user+action (e.g. on user message).

        Useful when a user interaction should reset the suppression
        window so the agent can act again immediately.
        """
        if action_type is ActionType.NOOP:
            return
        try:
            redis = get_redis()
            key = CacheKeys.agent_cooldown(user_id, action_type.value)
            await redis.delete(key)
        except Exception:
            log.warning(
                "agent_cd_reset_error",
                user_id=user_id,
                action=action_type.value,
                exc_info=True,
            )
