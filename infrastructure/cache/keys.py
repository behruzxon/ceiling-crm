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

    # AI rate limiting
    AI_RATE_LIMIT_WINDOW  = 65       # Per-user AI call sliding window (slightly > window)
    AI_DAILY_QUOTA        = 90_000   # 25 hours — per-tenant daily AI call counter

    # Lead cards (prevent duplicate sends)
    LEAD_CARD_SENT     = 300         # 5 min dedup window

    # Analytics cache
    DAILY_STATS        = 3_600       # 1 hour
    PIPELINE_COUNTS    = 300         # 5 min — frequently updated
    OWNER_ANALYTICS    = 60          # 1 min — short cache for owner dashboard

    # Broadcast dedup
    BROADCAST_USER_SENT = 86_400     # 24 hours — prevent re-send same broadcast

    # Group moderation
    MOD_LINK_WINDOW     = 600        # 10 min — link violation counter window

    # CTA inactivity feature
    CTA_SENT            = 172_800    # 2 days — dedup flag per user per calendar day

    # Group menu injection dedup
    GRP_MENU_SHOWN        = 86_400   # 24 hours — send selective keyboard at most once per user/day
    GRP_INLINE_MENU_SHOWN = 86_400   # 24 hours — send URL inline menu at most once per user/day

    # Catalog follow-up dedup (Madina AI)
    CATALOG_FOLLOWUP_SENT = 86_400   # 24 hours — at most one catalog follow-up per user/day

    # AI interaction follow-up nonce (Madina AI)
    AI_FOLLOWUP_NONCE     = 7_200    # 2 hours — auto-expires if user is completely inactive

    # AI lead score (Madina AI funnel)
    AI_LEAD_SCORE         = 2_592_000  # 30 days — persists across sessions

    # AI memory (Madina AI per-user context: name, district, area_m2, etc.)
    AI_MEMORY             = 2_592_000  # 30 days

    # AI follow-up reminder state + last interaction timestamp (Madina AI)
    AI_FOLLOWUP_STATE     = 86_400    # 24 hours — {first_sent, second_sent, lead_created}
    AI_LAST_INTERACTION   = 86_400    # 24 hours — unix timestamp of last user message

    # AI daily stats counters (Madina AI analytics)
    AI_STATS              = 172_800   # 48 hours — keeps today + yesterday for comparison
    AI_STATS_USER_DAY     = 90_000    # 25 hours — dedup flag: count each user once per day

    # Sales closer cooldown (Madina AI)
    SALES_CLOSER_COOLDOWN = 600       # 10 minutes — max one closing CTA per user per window

    # Billing notification dedup
    BILLING_NOTIFICATION  = 86_400    # 24 hours — prevent duplicate billing notifications

    # Subscription payment dedup
    SUBSCRIPTION_PAYMENT_LOCK = 300   # 5 min — prevent duplicate invoice creation

    # Sales escalation cooldown (AI Sales Agent)
    ESCALATION_COOLDOWN   = 1_800     # 30 minutes — max one escalation per user per window

    # Unified rate limiting (core.security.rate_limiter)
    RATE_USER_MSG_WINDOW    = 35      # slightly > 30s window
    RATE_TENANT_MSG_WINDOW  = 65      # slightly > 60s window
    RATE_AI_TENANT_WINDOW   = 65      # slightly > 60s window

    # AI response cache (core.services.ai_cache_service)
    AI_RESPONSE_CACHE       = 86_400  # 24 hours

    # AI knowledge base cache (core.services.ai_knowledge_service)
    AI_KNOWLEDGE_CACHE      = 600     # 10 minutes

    # Usage tracking (core.services.usage_service)
    MONTHLY_LEAD_COUNTER    = 2_764_800  # 32 days — monthly lead creation counter


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

    Multi-bot namespacing:
        User-scoped keys accept an optional ``bot_id`` parameter.
        When provided, a ``t:{bot_id}:`` prefix is prepended to prevent
        collisions when the same Telegram user interacts with multiple
        tenant bots.  When ``bot_id`` is None the key is unchanged
        (backward-compatible with single-bot mode).
    """

    @staticmethod
    def _ns(bot_id: int | None) -> str:
        """Return bot-scoped namespace prefix (empty string for single-bot)."""
        return f"t:{bot_id}:" if bot_id is not None else ""

    # ── User ──────────────────────────────────────────────────────────────
    @staticmethod
    def user_profile(user_id: int, *, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}user:{user_id}:profile"

    @staticmethod
    def user_role(user_id: int, *, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}user:{user_id}:role"

    # ── Group / Category ──────────────────────────────────────────────────
    @staticmethod
    def group_config(chat_id: int, *, bot_id: int | None = None) -> str:
        """Group metadata including category."""
        return f"{CacheKeys._ns(bot_id)}group:{chat_id}:config"

    @staticmethod
    def category_groups(*, bot_id: int | None = None) -> str:
        """Map of category → group_id list."""
        return f"{CacheKeys._ns(bot_id)}config:category_groups"

    # ── Pricing ───────────────────────────────────────────────────────────
    @staticmethod
    def base_price(category: str, *, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}price:base:{category}"

    @staticmethod
    def district_modifier(district: str, *, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}price:district:{district.lower().replace(' ', '_')}"

    @staticmethod
    def addon_prices(*, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}price:addons"

    # ── Rate limiting ─────────────────────────────────────────────────────
    @staticmethod
    def rate_limit(user_id: int, *, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}rl:{user_id}"

    # ── AI rate limiting ───────────────────────────────────────────────
    @staticmethod
    def ai_rate_limit(user_id: int, *, bot_id: int | None = None) -> str:
        """Per-user AI rate-limit identifier (passed to rate_limit_check).
        TTL: CacheTTL.AI_RATE_LIMIT_WINDOW.
        """
        return f"{CacheKeys._ns(bot_id)}ai:{user_id}"

    @staticmethod
    def ai_daily_quota(tenant_id: int, *, date_str: str) -> str:
        """Per-tenant daily AI usage counter (simple INCR key).
        date_str: ISO date, e.g. '2026-03-08'
        TTL: CacheTTL.AI_DAILY_QUOTA (25 hours).
        """
        return f"ai:quota:{tenant_id}:{date_str}"

    # ── Lead dedup (INTENTIONALLY GLOBAL: lead_id is unique DB PK) ──────
    @staticmethod
    def lead_card_sent(lead_id: int) -> str:
        """Prevent duplicate admin notifications for same lead."""
        return f"lead:{lead_id}:card_sent"

    # ── Analytics ────────────────────────────────────────────────────────
    @staticmethod
    def daily_stats(date_str: str, *, bot_id: int | None = None) -> str:
        """date_str format: YYYY-MM-DD"""
        return f"{CacheKeys._ns(bot_id)}analytics:daily:{date_str}"

    @staticmethod
    def pipeline_counts(*, bot_id: int | None = None) -> str:
        return f"{CacheKeys._ns(bot_id)}analytics:pipeline_counts"

    @staticmethod
    def owner_analytics(tenant_id: int, window_days: int) -> str:
        """Owner analytics summary cache per tenant + window.
        TTL: CacheTTL.OWNER_ANALYTICS (60 seconds).
        """
        return f"analytics:owner:{tenant_id}:{window_days}"

    # ── Broadcast dedup (INTENTIONALLY GLOBAL: broadcast_id is unique DB PK) ──
    @staticmethod
    def broadcast_sent(broadcast_id: int, user_id: int) -> str:
        return f"broadcast:{broadcast_id}:sent:{user_id}"

    # ── FSM helper (read-only metadata, not the state itself) ─────────────
    @staticmethod
    def user_active_category(user_id: int, *, bot_id: int | None = None) -> str:
        """The ceiling category a user is currently browsing."""
        return f"{CacheKeys._ns(bot_id)}user:{user_id}:active_category"

    # ── Group moderation ──────────────────────────────────────────────────
    @staticmethod
    def mod_link_violations(chat_id: int, user_id: int, *, bot_id: int | None = None) -> str:
        """Link violation counter per user per group (10-min window)."""
        return f"{CacheKeys._ns(bot_id)}mod:{chat_id}:link_violations:{user_id}"

    # ── CTA inactivity feature ────────────────────────────────────────────
    @staticmethod
    def cta_user_activity(*, bot_id: int | None = None) -> str:
        """Sorted set: member=str(user_id), score=unix_ts. Used for 5-min inactivity scan."""
        return f"{CacheKeys._ns(bot_id)}cta:user_activity"

    @staticmethod
    def cta_sent(user_id: int, date_str: str, *, bot_id: int | None = None) -> str:
        """Flag key (value '1'): set when a CTA was sent to this user today.

        date_str format: YYYY-MM-DD
        TTL: CacheTTL.CTA_SENT (2 days).
        """
        return f"{CacheKeys._ns(bot_id)}cta:sent:{user_id}:{date_str}"

    # ── Group menu injection ───────────────────────────────────────────────
    @staticmethod
    def grp_menu_shown(chat_id: int, user_id: int, *, bot_id: int | None = None) -> str:
        """Flag set when we've sent the selective ReplyKeyboard to this user in this group.

        TTL: CacheTTL.GRP_MENU_SHOWN (24 hours).
        """
        return f"{CacheKeys._ns(bot_id)}grp:menu:{chat_id}:{user_id}"

    @staticmethod
    def grp_inline_menu_shown(chat_id: int, user_id: int, *, bot_id: int | None = None) -> str:
        """Flag set when we've sent the URL inline menu to this user in this group.

        TTL: CacheTTL.GRP_INLINE_MENU_SHOWN (24 hours).
        """
        return f"{CacheKeys._ns(bot_id)}grp:inline_menu:{chat_id}:{user_id}"

    # ── Madina catalog follow-up ───────────────────────────────────────────
    @staticmethod
    def catalog_followup_sent(user_id: int, *, bot_id: int | None = None) -> str:
        """De-dup flag: set after sending catalog follow-up to this user.

        TTL: CacheTTL.CATALOG_FOLLOWUP_SENT (24 hours).
        """
        return f"{CacheKeys._ns(bot_id)}madina:catalog_followup:{user_id}"

    @staticmethod
    def ai_followup_nonce(user_id: int, *, bot_id: int | None = None) -> str:
        """Random nonce refreshed on every AI interaction.

        A scheduled reminder task compares its captured nonce to the stored value.
        If they differ (user interacted again) or the key expired (inactive >2 h),
        the reminder is suppressed.  TTL: CacheTTL.AI_FOLLOWUP_NONCE (2 hours).
        """
        return f"{CacheKeys._ns(bot_id)}madina:followup_nonce:{user_id}"

    @staticmethod
    def ai_lead_score(user_id: int, *, bot_id: int | None = None) -> str:
        """0-100 numeric lead score for Madina AI funnel.

        Incremented by funnel events (area +15, district +10, order +25, phone +40, etc.).
        TTL: CacheTTL.AI_LEAD_SCORE (30 days).
        """
        return f"{CacheKeys._ns(bot_id)}ai:score:{user_id}"

    @staticmethod
    def ai_memory(user_id: int, *, bot_id: int | None = None) -> str:
        """Per-user AI memory blob: name, district, area_m2, design_type, lead_score,
        last_user_message, phone_captured, updated_at.
        TTL: CacheTTL.AI_MEMORY (30 days).
        """
        return f"{CacheKeys._ns(bot_id)}ai:memory:{user_id}"

    @staticmethod
    def ai_followup_state(user_id: int, *, bot_id: int | None = None) -> str:
        """Follow-up reminder state: {first_sent, second_sent, lead_created}.
        Reset on each new interaction (preserves lead_created).
        TTL: CacheTTL.AI_FOLLOWUP_STATE (24 hours).
        """
        return f"{CacheKeys._ns(bot_id)}ai:followup_state:{user_id}"

    @staticmethod
    def ai_last_interaction(user_id: int, *, bot_id: int | None = None) -> str:
        """Unix timestamp of the user's last AI interaction (str).
        TTL: CacheTTL.AI_LAST_INTERACTION (24 hours).
        """
        return f"{CacheKeys._ns(bot_id)}ai:last_interaction:{user_id}"

    @staticmethod
    def ai_stats_field(date_str: str, field: str, *, bot_id: int | None = None) -> str:
        """Daily AI stats counter for one metric.

        date_str: ISO date, e.g. '2026-03-05'
        field: one of users_started | messages_total | lead_hot | lead_warm |
               lead_cold | phones_received | orders_started
        TTL: CacheTTL.AI_STATS (48 hours).
        """
        return f"{CacheKeys._ns(bot_id)}ai:stats:{date_str}:{field}"

    @staticmethod
    def ai_stats_user_day(date_str: str, user_id: int, *, bot_id: int | None = None) -> str:
        """Dedup flag: set (NX) when a user is counted in users_started for the day.
        TTL: CacheTTL.AI_STATS_USER_DAY (25 hours).
        """
        return f"{CacheKeys._ns(bot_id)}ai:stats:user:{date_str}:{user_id}"

    # ── Sales closer ─────────────────────────────────────────────────────
    @staticmethod
    def sales_closer_last(user_id: int, *, bot_id: int | None = None) -> str:
        """Cooldown flag: set (NX) when a closing CTA is sent to this user.
        TTL: CacheTTL.SALES_CLOSER_COOLDOWN (10 minutes).
        """
        return f"{CacheKeys._ns(bot_id)}closer:last:{user_id}"

    # ── Sales escalation ──────────────────────────────────────────────
    @staticmethod
    def escalation_last(user_id: int, *, bot_id: int | None = None) -> str:
        """Cooldown flag: set (NX) when an escalation is sent for this user.
        TTL: CacheTTL.ESCALATION_COOLDOWN (30 minutes).
        """
        return f"{CacheKeys._ns(bot_id)}escalation:last:{user_id}"

    # ── AI response cache (core.services.ai_cache_service) ──────────────
    @staticmethod
    def ai_response_cache(tenant_id: int | None, msg_hash: str) -> str:
        """Cached AI response. Format: ai_cache:{tid}:{hash}.
        TTL: CacheTTL.AI_RESPONSE_CACHE (24 hours).
        """
        tid = tenant_id or 0
        return f"ai_cache:{tid}:{msg_hash}"

    # ── Unified rate limiting (core.security.rate_limiter) ──────────────
    @staticmethod
    def rate_user_msg(tenant_id: int | None, user_id: int) -> str:
        """Per-user message rate limit. Format: rate:user:{tid}:{uid}."""
        tid = tenant_id or 0
        return f"rate:user:{tid}:{user_id}"

    @staticmethod
    def rate_tenant_msg(tenant_id: int) -> str:
        """Per-tenant message rate limit. Format: rate:tenant:{tid}."""
        return f"rate:tenant:{tenant_id}"

    @staticmethod
    def rate_ai_tenant(tenant_id: int) -> str:
        """Per-tenant AI call rate limit. Format: rate:ai:{tid}."""
        return f"rate:ai:{tenant_id}"

    # ── AI knowledge base cache (core.services.ai_knowledge_service) ──
    @staticmethod
    def ai_knowledge(tenant_id: int) -> str:
        """All knowledge entries for a tenant (JSON list).
        TTL: CacheTTL.AI_KNOWLEDGE_CACHE (10 minutes).
        """
        return f"ai_kb:{tenant_id}"

    # ── Usage tracking (core.services.usage_service) ──────────────────
    @staticmethod
    def monthly_lead_count(tenant_id: int, *, year_month: str) -> str:
        """Per-tenant monthly lead creation counter (simple INCR key).
        year_month: e.g. '2026-03'
        TTL: CacheTTL.MONTHLY_LEAD_COUNTER (32 days).
        """
        return f"usage:leads:{tenant_id}:{year_month}"

    # ── Billing (INTENTIONALLY GLOBAL: scoped by tenant_id in key) ────
    @staticmethod
    def subscription_payment_lock(tenant_id: int) -> str:
        """Lock to prevent duplicate invoice creation for a tenant.
        TTL: CacheTTL.SUBSCRIPTION_PAYMENT_LOCK (5 min).
        """
        return f"billing:pay_lock:{tenant_id}"

    @staticmethod
    def billing_notification_sent(tenant_id: int, notification_type: str) -> str:
        """Dedup flag to prevent duplicate billing notifications.

        notification_type: "3day" | "1day" | "expired"
        TTL: CacheTTL.BILLING_NOTIFICATION (24 hours).
        """
        return f"billing:notif:{tenant_id}:{notification_type}"
