"""
infrastructure.cache.keys
~~~~~~~~~~~~~~~~~~~~~~~~~
Centralised Redis key namespace definitions.

ALL Redis keys must be defined here — never use raw strings in application code.
This ensures:
1. No key collisions across features
2. Easy TTL management in one place
3. Simple key auditing and documentation

Usage:
    from infrastructure.cache.keys import CacheKeys
    key = CacheKeys.user_profile(user_id=42)       # "user:42:profile"
    ttl = CacheTTL.USER_PROFILE                    # 3600
"""

from __future__ import annotations
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# TTL constants (seconds)
# ─────────────────────────────────────────────────────────────────────────────

class CacheTTL:
    """All TTL values in seconds. Reference in set() calls."""

    # User data
    USER_PROFILE       = 3_600       # 1 hour
    USER_ROLE          = 3_600       # 1 hour

    # Group / category resolution
    GROUP_CONFIG       = 3_600       # 1 hour — refreshed by cache_warmup job
    CATEGORY_MAPPING   = 3_600       # chat_id → category mapping

    # Pricing (refreshed every 30 min by scheduler)
    PRICE_CONFIG       = 1_800       # 30 min
    DISTRICT_MODIFIERS = 1_800       # 30 min

    # FSM states (managed by aiogram RedisStorage)
    FSM_STATE          = 86_400      # 24 hours

    # Rate limiting
    RATE_LIMIT_WINDOW  = 65          # Slightly longer than window to handle edge

    # Lead cards (prevent duplicate sends)
    LEAD_CARD_SENT     = 300         # 5 min dedup window

    # Analytics cache
    DAILY_STATS        = 3_600       # 1 hour
    PIPELINE_COUNTS    = 300         # 5 min — frequently updated

    # Broadcast dedup
    BROADCAST_USER_SENT = 86_400     # 24 hours — prevent re-send same broadcast

    # Group moderation
    MOD_LINK_WINDOW     = 600        # 10 min — link violation counter window

    # CTA inactivity feature
    CTA_SENT            = 172_800    # 2 days — dedup flag per user per calendar day

    # Group menu injection dedup
    GRP_MENU_SHOWN      = 86_400     # 24 hours — send selective keyboard at most once per user/day


# ─────────────────────────────────────────────────────────────────────────────
# Key builders — all return unprefixed keys (prefix added by CacheClient)
# ─────────────────────────────────────────────────────────────────────────────

class CacheKeys:
    """
    Centralised key builders.
    All methods return strings WITHOUT the app prefix.
    The prefix (ccrm:) is added by CacheClient._key().

    Key naming convention:
        {entity}:{id}:{attribute}
    """

    # ── User ──────────────────────────────────────────────────────────────
    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"user:{user_id}:profile"

    @staticmethod
    def user_role(user_id: int) -> str:
        return f"user:{user_id}:role"

    # ── Group / Category ──────────────────────────────────────────────────
    @staticmethod
    def group_config(chat_id: int) -> str:
        """Group metadata including category."""
        return f"group:{chat_id}:config"

    @staticmethod
    def category_groups() -> str:
        """Map of category → group_id list."""
        return "config:category_groups"

    # ── Pricing ───────────────────────────────────────────────────────────
    @staticmethod
    def base_price(category: str) -> str:
        return f"price:base:{category}"

    @staticmethod
    def district_modifier(district: str) -> str:
        return f"price:district:{district.lower().replace(' ', '_')}"

    @staticmethod
    def addon_prices() -> str:
        return "price:addons"

    # ── Rate limiting ─────────────────────────────────────────────────────
    @staticmethod
    def rate_limit(user_id: int) -> str:
        return f"rl:{user_id}"

    # ── Lead dedup ────────────────────────────────────────────────────────
    @staticmethod
    def lead_card_sent(lead_id: int) -> str:
        """Prevent duplicate admin notifications for same lead."""
        return f"lead:{lead_id}:card_sent"

    # ── Analytics ────────────────────────────────────────────────────────
    @staticmethod
    def daily_stats(date_str: str) -> str:
        """date_str format: YYYY-MM-DD"""
        return f"analytics:daily:{date_str}"

    @staticmethod
    def pipeline_counts() -> str:
        return "analytics:pipeline_counts"

    # ── Broadcast dedup ───────────────────────────────────────────────────
    @staticmethod
    def broadcast_sent(broadcast_id: int, user_id: int) -> str:
        return f"broadcast:{broadcast_id}:sent:{user_id}"

    # ── FSM helper (read-only metadata, not the state itself) ─────────────
    @staticmethod
    def user_active_category(user_id: int) -> str:
        """The ceiling category a user is currently browsing."""
        return f"user:{user_id}:active_category"

    # ── Group moderation ──────────────────────────────────────────────────
    @staticmethod
    def mod_link_violations(chat_id: int, user_id: int) -> str:
        """Link violation counter per user per group (10-min window)."""
        return f"mod:{chat_id}:link_violations:{user_id}"

    # ── CTA inactivity feature ────────────────────────────────────────────
    @staticmethod
    def cta_user_activity() -> str:
        """Sorted set: member=str(user_id), score=unix_ts. Used for 5-min inactivity scan."""
        return "cta:user_activity"

    @staticmethod
    def cta_sent(user_id: int, date_str: str) -> str:
        """Flag key (value '1'): set when a CTA was sent to this user today.

        date_str format: YYYY-MM-DD
        TTL: CacheTTL.CTA_SENT (2 days).
        """
        return f"cta:sent:{user_id}:{date_str}"

    # ── Group menu injection ───────────────────────────────────────────────
    @staticmethod
    def grp_menu_shown(chat_id: int, user_id: int) -> str:
        """Flag set when we've sent the selective ReplyKeyboard to this user in this group.

        TTL: CacheTTL.GRP_MENU_SHOWN (24 hours).
        """
        return f"grp:menu:{chat_id}:{user_id}"
