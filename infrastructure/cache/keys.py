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

    # AI daily rate limit (per-user)
    AI_RATE_LIMIT_DAILY   = 90_000    # 25 hours — expires just past midnight

    # AI sales advice cache (per lead)
    AI_LEAD_ADVICE        = 1_800     # 30 minutes — avoid excessive OpenAI calls

    # Conversation intelligence dedup
    CONV_INTEL_ALERT        = 3_600   # 1 hour — one insight alert per lead per hour
    CONV_MGR_DELAY_ALERT    = 1_800   # 30 minutes — one manager delay alert per lead
    CONV_COOLING_ALERT      = 7_200   # 2 hours — one cooling alert per lead

    # Sales autopilot dedup
    AUTOPILOT_OPPORTUNITY   = 7_200   # 2 hours — one opportunity alert per lead
    AUTOPILOT_RISK          = 3_600   # 1 hour — one risk alert per lead
    AUTOPILOT_CLOSING       = 7_200   # 2 hours — one closing suggestion per lead

    # AI Closer dedup
    CLOSING_OPPORTUNITY     = 7_200   # 2 hours — one closing readiness alert per lead
    CLOSING_LOSS_RISK       = 3_600   # 1 hour — one close-loss risk alert per lead

    # Auto-seller
    AUTO_REPLY_CONSECUTIVE  = 3_600   # 1 hour — consecutive auto-reply counter TTL
    AUTO_SALES_ESCALATION   = 3_600   # 1 hour — dedup escalation alerts per lead
    AUTO_REPLY_LOG          = 86_400  # 24 hours — last auto-reply metadata

    # Adaptive weights (outcome-based learning)
    ADAPTIVE_WEIGHTS        = 7_200   # 2 hours — refreshed every 1 hour by scheduler

    # Agent follow-up engine
    AGENT_FU_CATALOG        = 86_400  # 24h — catalog follow-up dedup
    AGENT_FU_PRICE          = 7_200   # 2h — price follow-up dedup
    AGENT_FU_ORDER          = 21_600  # 6h — abandoned order follow-up dedup
    AGENT_FU_DAILY_COUNT    = 90_000  # 25h — daily follow-up counter
    AGENT_FU_LAST_SENT      = 600     # 10 min — min gap between follow-ups


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

    @staticmethod
    def grp_inline_menu_shown(chat_id: int, user_id: int) -> str:
        """Flag set when we've sent the URL inline menu to this user in this group.

        TTL: CacheTTL.GRP_INLINE_MENU_SHOWN (24 hours).
        """
        return f"grp:inline_menu:{chat_id}:{user_id}"

    # ── Madina catalog follow-up ───────────────────────────────────────────
    @staticmethod
    def catalog_followup_sent(user_id: int) -> str:
        """De-dup flag: set after sending catalog follow-up to this user.

        TTL: CacheTTL.CATALOG_FOLLOWUP_SENT (24 hours).
        """
        return f"madina:catalog_followup:{user_id}"

    @staticmethod
    def ai_followup_nonce(user_id: int) -> str:
        """Random nonce refreshed on every AI interaction.

        A scheduled reminder task compares its captured nonce to the stored value.
        If they differ (user interacted again) or the key expired (inactive >2 h),
        the reminder is suppressed.  TTL: CacheTTL.AI_FOLLOWUP_NONCE (2 hours).
        """
        return f"madina:followup_nonce:{user_id}"

    @staticmethod
    def ai_lead_score(user_id: int) -> str:
        """0-100 numeric lead score for Madina AI funnel.

        Incremented by funnel events (area +15, district +10, order +25, phone +40, etc.).
        TTL: CacheTTL.AI_LEAD_SCORE (30 days).
        """
        return f"ai:score:{user_id}"

    @staticmethod
    def ai_memory(user_id: int) -> str:
        """Per-user AI memory blob: name, district, area_m2, design_type, lead_score,
        last_user_message, phone_captured, updated_at.
        TTL: CacheTTL.AI_MEMORY (30 days).
        """
        return f"ai:memory:{user_id}"

    @staticmethod
    def ai_followup_state(user_id: int) -> str:
        """Follow-up reminder state: {first_sent, second_sent, lead_created}.
        Reset on each new interaction (preserves lead_created).
        TTL: CacheTTL.AI_FOLLOWUP_STATE (24 hours).
        """
        return f"ai:followup_state:{user_id}"

    @staticmethod
    def ai_last_interaction(user_id: int) -> str:
        """Unix timestamp of the user's last AI interaction (str).
        TTL: CacheTTL.AI_LAST_INTERACTION (24 hours).
        """
        return f"ai:last_interaction:{user_id}"

    @staticmethod
    def ai_stats_field(date_str: str, field: str) -> str:
        """Daily AI stats counter for one metric.

        date_str: ISO date, e.g. '2026-03-05'
        field: one of users_started | messages_total | lead_hot | lead_warm |
               lead_cold | phones_received | orders_started
        TTL: CacheTTL.AI_STATS (48 hours).
        """
        return f"ai:stats:{date_str}:{field}"

    @staticmethod
    def ai_stats_user_day(date_str: str, user_id: int) -> str:
        """Dedup flag: set (NX) when a user is counted in users_started for the day.
        TTL: CacheTTL.AI_STATS_USER_DAY (25 hours).
        """
        return f"ai:stats:user:{date_str}:{user_id}"

    # ── Sales closer ─────────────────────────────────────────────────────
    @staticmethod
    def sales_closer_last(user_id: int) -> str:
        """Cooldown flag: set (NX) when a closing CTA is sent to this user.
        TTL: CacheTTL.SALES_CLOSER_COOLDOWN (10 minutes).
        """
        return f"closer:last:{user_id}"

    # ── AI daily rate limit ────────────────────────────────────────────────
    @staticmethod
    def ai_rate_limit_daily(user_id: int) -> str:
        """Counter: incremented on each AI call. Resets daily via TTL.
        TTL: CacheTTL.AI_RATE_LIMIT_DAILY (25 hours).
        """
        return f"ai:calls:{user_id}"

    @staticmethod
    def ai_lead_advice(lead_id: int) -> str:
        """Cached AI sales advice for a lead.
        TTL: CacheTTL.AI_LEAD_ADVICE (30 minutes).
        """
        return f"ai:lead_advice:{lead_id}"

    # ── Conversation intelligence ────────────────────────────────────
    @staticmethod
    def conv_intel_alert(lead_id: int) -> str:
        """Dedup: one conversation insight alert per lead per cycle.
        TTL: CacheTTL.CONV_INTEL_ALERT (1 hour).
        """
        return f"conv:alert:{lead_id}"

    @staticmethod
    def conv_mgr_delay_alert(lead_id: int) -> str:
        """Dedup: one manager delay alert per lead per cycle.
        TTL: CacheTTL.CONV_MGR_DELAY_ALERT (30 minutes).
        """
        return f"conv:mgr_delay:{lead_id}"

    @staticmethod
    def conv_cooling_alert(lead_id: int) -> str:
        """Dedup: one cooling alert per lead per cycle.
        TTL: CacheTTL.CONV_COOLING_ALERT (2 hours).
        """
        return f"conv:cooling:{lead_id}"

    # ── Sales autopilot ────────────────────────────────────────────
    @staticmethod
    def autopilot_opportunity(lead_id: int) -> str:
        """Dedup: one opportunity alert per lead per cycle.
        TTL: CacheTTL.AUTOPILOT_OPPORTUNITY (2 hours).
        """
        return f"autopilot:opp:{lead_id}"

    @staticmethod
    def autopilot_risk(lead_id: int) -> str:
        """Dedup: one risk alert per lead per cycle.
        TTL: CacheTTL.AUTOPILOT_RISK (1 hour).
        """
        return f"autopilot:risk:{lead_id}"

    @staticmethod
    def autopilot_closing(lead_id: int) -> str:
        """Dedup: one closing suggestion per lead per cycle.
        TTL: CacheTTL.AUTOPILOT_CLOSING (2 hours).
        """
        return f"autopilot:closing:{lead_id}"

    # ── AI Closer ─────────────────────────────────────────────────────
    @staticmethod
    def closing_opportunity(lead_id: int) -> str:
        """Dedup: one closing readiness alert per lead per cycle.
        TTL: CacheTTL.CLOSING_OPPORTUNITY (2 hours).
        """
        return f"closer:opp:{lead_id}"

    @staticmethod
    def closing_loss_risk(lead_id: int) -> str:
        """Dedup: one close-loss risk alert per lead per cycle.
        TTL: CacheTTL.CLOSING_LOSS_RISK (1 hour).
        """
        return f"closer:risk:{lead_id}"

    # ── Auto-seller ──────────────────────────────────────────────────
    @staticmethod
    def auto_reply_consecutive(user_id: int) -> str:
        """Counter: consecutive auto-replies sent to this user.
        TTL: CacheTTL.AUTO_REPLY_CONSECUTIVE (1 hour).
        """
        return f"autosell:consec:{user_id}"

    @staticmethod
    def auto_sales_escalation(lead_id: int) -> str:
        """Dedup: one escalation alert per lead per cycle.
        TTL: CacheTTL.AUTO_SALES_ESCALATION (1 hour).
        """
        return f"autosell:esc:{lead_id}"

    @staticmethod
    def auto_reply_log(user_id: int) -> str:
        """Last auto-reply metadata (JSON: reply_type, timestamp).
        TTL: CacheTTL.AUTO_REPLY_LOG (24 hours).
        """
        return f"autosell:log:{user_id}"

    # ── Adaptive weights (outcome-based learning) ─────────────────────
    @staticmethod
    def adaptive_weights(event_type: str) -> str:
        """Cached adaptive tactic weights JSON for an event type.
        TTL: CacheTTL.ADAPTIVE_WEIGHTS (2 hours).
        """
        return f"adaptive_weights:{event_type}"

    # ── Agent follow-up engine ────────────────────────────────────────
    @staticmethod
    def agent_fu_dedup(user_id: int, fu_type: str) -> str:
        """Per-type dedup: set NX when follow-up is sent.
        TTL: AGENT_FU_CATALOG / AGENT_FU_PRICE / AGENT_FU_ORDER.
        """
        return f"agent:fu:{fu_type}:{user_id}"

    @staticmethod
    def agent_fu_daily(user_id: int) -> str:
        """Daily counter: INCR on each follow-up sent.
        TTL: CacheTTL.AGENT_FU_DAILY_COUNT (25h).
        """
        return f"agent:fu:daily:{user_id}"

    @staticmethod
    def agent_fu_last(user_id: int) -> str:
        """Min-gap enforcer: set NX after sending.
        TTL: CacheTTL.AGENT_FU_LAST_SENT (10 min).
        """
        return f"agent:fu:last:{user_id}"
