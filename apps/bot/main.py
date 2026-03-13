"""
apps.bot.main
~~~~~~~~~~~~~
Application entry point for the Telegram bot.

Bootstrap order:
1. Configure structured logging
2. Initialise Sentry error tracking
3. Connect to PostgreSQL + Redis
4. Build aiogram Bot + Dispatcher
5. Register middlewares (order is significant)
6. Mount all routers
7. Start webhook or polling based on environment

This file should contain ONLY wiring.  All business logic
lives in handlers/, middlewares/, and core/.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

import sentry_sdk
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.strategy import FSMStrategy
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from apps.bot.handlers.admin.broadcasts import router as broadcasts_router
from apps.bot.handlers.admin.analytics import router as analytics_router
from apps.bot.handlers.admin.dashboard import router as dashboard_router
from apps.bot.handlers.admin.lead_status import router as lead_status_router
from apps.bot.handlers.admin.leads import router as admin_leads_router
from apps.bot.handlers.admin.media import router as media_router
from apps.bot.handlers.admin.operator_stats import router as operator_stats_router
from apps.bot.handlers.admin.pipeline import router as pipeline_router
from apps.bot.handlers.admin.radar import router as radar_router
from apps.bot.handlers.admin.lead_advice import router as lead_advice_router
from apps.bot.handlers.admin.reports import router as reports_router
from apps.bot.handlers.admin.sales_report import router as sales_report_router
from apps.bot.handlers.admin.stats import router as stats_router
from apps.bot.handlers.admin.system_status import router as system_status_router
from apps.bot.handlers.admin.scheduler import router as scheduler_router
from apps.bot.handlers.admin.autopilot import router as autopilot_router
from apps.bot.handlers.admin.close_advice import router as close_advice_router
from apps.bot.handlers.callbacks.cta_callbacks import router as cta_callbacks_router
from apps.bot.handlers.callbacks.kanban_callbacks import router as kanban_callbacks_router
from apps.bot.handlers.callbacks.lead_callbacks import router as lead_callbacks_router
from apps.bot.handlers.callbacks.package_callbacks import router as package_callbacks_router
from apps.bot.handlers.callbacks.payment_callbacks import router as payment_callbacks_router
from apps.bot.handlers.callbacks.pipeline_callbacks import router as pipeline_callbacks_router
from apps.bot.handlers.callbacks.operator_callbacks import router as operator_callbacks_router
from apps.bot.handlers.callbacks.sales_closer_callbacks import router as sales_closer_callbacks_router
from apps.bot.handlers.group.admin import router as group_admin_router
from apps.bot.handlers.group.start import router as group_start_router
from apps.bot.handlers.group.admin_group_tracker import router as admin_group_tracker_router
from apps.bot.handlers.group.member_status import router as member_status_router
from apps.bot.handlers.group.messages import router as group_messages_router
from apps.bot.handlers.group.moderation import router as moderation_router
from apps.bot.handlers.group.welcome import router as welcome_router
from apps.bot.handlers.private.about import router as about_router
from apps.bot.handlers.private.packages import router as packages_router
from apps.bot.handlers.private.ai_support import router as ai_support_router
from apps.bot.handlers.private.catalog import router as catalog_router
from apps.bot.handlers.private.lead_capture import router as lead_capture_router
from apps.bot.handlers.private.my_orders import router as my_orders_router
from apps.bot.handlers.private.measurement_lead import router as measurement_lead_router
from apps.bot.handlers.private.operator import router as operator_router
from apps.bot.handlers.private.payment import router as payment_router
from apps.bot.handlers.private.order import router as order_router
from apps.bot.handlers.private.pricing import router as pricing_router
from apps.bot.handlers.private.promotions import router as promotions_router
from apps.bot.handlers.private.support import router as support_router
from apps.bot.tasks import daily_report, inactive_cta
from apps.bot.handlers.error_handler import register_error_handler
from apps.bot.middlewares.audit import AuditMiddleware
from apps.bot.middlewares.auth import AuthMiddleware
from apps.bot.middlewares.group_context import GroupContextMiddleware
from apps.bot.middlewares.group_menu_injector import GroupMenuInjectorMiddleware
from apps.bot.middlewares.locale import LocaleMiddleware
from apps.bot.middlewares.rate_limit import RateLimitMiddleware
from apps.bot.middlewares.security import SecurityMiddleware
from infrastructure.cache.client import connect_redis, disconnect_redis, get_sessions_redis
from infrastructure.database.session import connect_database, disconnect_database
from infrastructure.monitoring.prometheus import setup_prometheus
from shared.config import get_settings
from shared.logging import configure_logging, get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Bot Commands (shown in Telegram menu)
# ─────────────────────────────────────────────────────────────────────────────

BOT_COMMANDS: list[BotCommand] = [
    BotCommand(command="start",   description="Botni ishga tushirish / Start"),
    BotCommand(command="menu",    description="Asosiy menyuni ko'rsatish"),
    BotCommand(command="catalog", description="Patalok katalogi"),
    BotCommand(command="price",   description="Narxni hisoblash"),
    BotCommand(command="order",   description="Buyurtma berish"),
    BotCommand(command="help",    description="Yordam"),
    BotCommand(command="cancel",  description="Amalni bekor qilish"),
    BotCommand(command="ai_off",  description="AI rejimdan chiqish"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher & Router Assembly
# ─────────────────────────────────────────────────────────────────────────────


def build_dispatcher(storage: RedisStorage) -> Dispatcher:
    """
    Construct the Dispatcher and register all middleware + routers.

    Router priority (top = highest priority):
        1. Admin handlers   — gated by RoleFilter
        2. Callback handlers — inline keyboard callbacks
        3. Group handlers    — group-specific events
        4. Private handlers  — DM conversation flows

    Middleware execution order (outer → inner for requests,
    inner → outer for responses):
        AuthMiddleware → LocaleMiddleware → GroupContextMiddleware
        → RateLimitMiddleware → AuditMiddleware
    """
    dp = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_CHAT,  # separate FSM per user per chat
    )

    # ── Outer middlewares (run for every update) ──────────────────────────
    # Order matters: each wraps the next.
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.outer_middleware(SecurityMiddleware())
    dp.update.outer_middleware(LocaleMiddleware())
    dp.update.outer_middleware(GroupContextMiddleware())
    dp.update.outer_middleware(RateLimitMiddleware())
    dp.update.outer_middleware(AuditMiddleware())

    # ── Global error handler (logs unhandled exceptions to system_errors) ──
    register_error_handler(dp)
    dp.message.outer_middleware(GroupMenuInjectorMiddleware())  # inject selective ReplyKeyboard in groups

    # ── Admin router (restricted access) ──────────────────────────────────
    admin_router = Router(name="admin")
    admin_router.include_routers(
        dashboard_router,
        admin_leads_router,
        pipeline_router,
        radar_router,
        analytics_router,
        sales_report_router,
        lead_advice_router,
        broadcasts_router,
        scheduler_router,
        operator_stats_router,
        reports_router,
        media_router,
        autopilot_router,      # /autopilot — AI sales autopilot suggestions
        close_advice_router,   # /close_advice — AI closer readiness + tactic
        stats_router,          # /stats + stats:period:* callbacks
        system_status_router,  # /system_status diagnostics
    )

    # ── Callbacks router ───────────────────────────────────────────────────
    callbacks_router = Router(name="callbacks")
    callbacks_router.include_routers(
        lead_callbacks_router,
        kanban_callbacks_router,    # kanban:* — visual pipeline management
        lead_status_router,         # lead:{id}:status:{status} — quick admin status updates
        cta_callbacks_router,       # cta:* — discount / order / pricing / operator / catalog
        sales_closer_callbacks_router,  # closer:* — AI sales closer CTA buttons
        operator_callbacks_router,     # op:* — on-demand operator assist suggestions
        pipeline_callbacks_router,
        payment_callbacks_router,
        package_callbacks_router,   # pkg:admin:* inline buttons from notifications
    )

    # ── Group router ───────────────────────────────────────────────────────
    group_router = Router(name="group")
    group_router.include_routers(
        group_admin_router,         # /admin command + gs: callbacks — must be first
        group_start_router,         # /start + /menu in groups → inline keyboard + grpmenu:* callbacks
        admin_group_tracker_router, # my_chat_member → upsert admin_groups + send menu
        welcome_router,             # chat_member: join welcome + analytics — before any other chat_member handler
        member_status_router,       # my_chat_member: bot add/remove log only (no chat_member handlers)
        # NOTE: moderation_router is intentionally NOT here.
        # It has a bare F.chat.type catch-all for group messages — placing it inside
        # group_router (before private_router) would swallow every menu button tap
        # before the BTN_* text handlers in private_router ever see it.
        # It is registered at the dispatcher level AFTER private_router, mirroring
        # the same reasoning that keeps group_messages_router last.
    )

    # ── Private DM router ─────────────────────────────────────────────────
    private_router = Router(name="private")
    private_router.include_routers(
        support_router,      # /start /help /cancel — commands must win over any catch-all
        catalog_router,
        promotions_router,   # simple text+callback handler — no FSM state deps
        about_router,        # simple text+callback handler — owns open_catalog callback
        packages_router,     # "📦 Tayyor paketlar" + pkg:detail/order/calc callbacks
        pricing_router,
        my_orders_router,    # must precede order_router (shares "📦" prefix text)
        payment_router,      # FSM — must precede lead_capture_router catch-all
        order_router,        # must precede lead_capture_router
        operator_router,          # must precede ai_support_router
        measurement_lead_router,  # FSM for bepul o'lchov — before ai_support catch-all
        lead_capture_router,
        ai_support_router,  # free-text catch-all — commands already excluded by guard
    )

    # Mount all top-level routers into Dispatcher.
    #
    # Router priority (highest → lowest):
    #   admin_router      — role-gated admin commands + callbacks
    #   callbacks_router  — all inline-button callbacks (kanban:, cta:, pkg:, etc.)
    #   group_router      — /start /menu + my_chat_member/chat_member events
    #   private_router    — DM flows that also serve groups (BTN_* text handlers)
    #   moderation_router — link/flood guard; must run AFTER private_router so
    #                       menu button taps reach BTN_* handlers first
    #   group_messages_router — silent catch-all; always last
    dp.include_routers(
        admin_router,
        callbacks_router,
        group_router,
        private_router,
        moderation_router,      # after private so BTN_* text taps reach private first
        group_messages_router,  # silent catch-all — always last
    )

    log.info(
        "dispatcher_built",
        routers=[r.name for r in dp.sub_routers],
    )
    return dp


# ─────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def _preflight_checks() -> None:
    """Fail-fast validation of critical config before connecting to services."""
    settings = get_settings()
    errors: list[str] = []

    # Bot token basic format check (should contain a colon)
    token = settings.bot.token.get_secret_value()
    if ":" not in token or len(token) < 20:
        errors.append("BOT_TOKEN looks invalid (missing ':' or too short)")

    # OpenAI key must be set
    api_key = settings.openai.api_key.get_secret_value()
    if not api_key or api_key in ("sk-...", "your-key-here", "CHANGE_ME"):
        errors.append("OPENAI_API_KEY is missing or placeholder")

    # admin_group_id must be negative (Telegram group IDs are negative)
    if settings.bot.admin_group_id >= 0:
        errors.append(
            f"BOT_ADMIN_GROUP_ID={settings.bot.admin_group_id} should be negative "
            "(Telegram group/supergroup IDs are negative)"
        )

    # Database URL must resolve (host present)
    if not settings.db.host or not settings.db.password.get_secret_value():
        errors.append("POSTGRES_HOST or POSTGRES_PASSWORD is missing")

    # Redis URL must resolve
    if not settings.redis.host:
        errors.append("REDIS_HOST is missing")

    # Webhook secret required when webhook mode is enabled
    if settings.bot.webhook_url:
        ws = settings.bot.webhook_secret
        if not ws or not ws.get_secret_value():
            errors.append(
                "BOT_WEBHOOK_SECRET is required when BOT_WEBHOOK_URL is set"
            )

    if errors:
        for err in errors:
            log.error("preflight_check_failed", detail=err)
        raise SystemExit(f"Preflight checks failed:\n" + "\n".join(f"  - {e}" for e in errors))

    log.info("preflight_checks_passed")


async def on_startup(bot: Bot) -> None:
    """
    Called once when the bot application starts.
    Initialises all external connections and registers bot commands.
    """
    log.info("bot_startup_begin")

    _preflight_checks()

    # Connect to databases
    await connect_database()
    await connect_redis()

    # Register bot commands in Telegram UI
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())

    settings = get_settings()

    # Register webhook if in production/staging
    if settings.bot.webhook_url:
        await bot.set_webhook(
            url=f"{settings.bot.webhook_url}/webhook",
            secret_token=settings.bot.webhook_secret.get_secret_value()
            if settings.bot.webhook_secret
            else None,
            drop_pending_updates=True,
            max_connections=settings.bot.max_connections,
        )
        log.info("webhook_registered", url=settings.bot.webhook_url)
    else:
        # Polling mode: remove any existing webhook
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("polling_mode_active")

    daily_report.start(bot)
    inactive_cta.start(bot)

    log.info("bot_startup_complete")


async def on_shutdown(bot: Bot) -> None:
    """
    Called on graceful shutdown.
    Closes all connections and removes webhook.
    """
    log.info("bot_shutdown_begin")

    settings = get_settings()
    if settings.bot.webhook_url:
        await bot.delete_webhook()

    daily_report.stop()
    inactive_cta.stop()

    await disconnect_database()
    await disconnect_redis()
    await bot.session.close()

    log.info("bot_shutdown_complete")


# ─────────────────────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────────────────────


def create_bot() -> Bot:
    """Instantiate the aiogram Bot with settings."""
    settings = get_settings()
    return Bot(
        token=settings.bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=settings.bot.parse_mode),
    )


async def create_storage() -> RedisStorage:
    """Create Redis FSM storage for state persistence across restarts."""
    settings = get_settings()
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(
        settings.redis.sessions_url,
        decode_responses=True,
    )
    return RedisStorage(redis=redis_client)


# ─────────────────────────────────────────────────────────────────────────────
# Entry points: polling vs webhook
# ─────────────────────────────────────────────────────────────────────────────


async def run_polling() -> None:
    """
    Run the bot in long-polling mode.
    Used for local development.  Not suitable for production.
    """
    bot = create_bot()
    storage = await create_storage()
    dp = build_dispatcher(storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    log.info("starting_polling")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
                "chat_member",
                "my_chat_member",
            ],
            handle_signals=True,
        )
    finally:
        log.info("polling_stopped")


async def create_bot_async() -> tuple[Bot, Dispatcher]:
    b = create_bot()
    s = await create_storage()
    d = build_dispatcher(s)
    d.startup.register(on_startup)
    d.shutdown.register(on_shutdown)
    return b, d


async def build_web_app() -> web.Application:
    settings = get_settings()

    bot, dp = await create_bot_async()

    app = web.Application()

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=(
            settings.bot.webhook_secret.get_secret_value()
            if settings.bot.webhook_secret
            else None
        ),
    ).register(app, path="/webhook")

    setup_application(app, dp, bot=bot)

    setup_prometheus(app)  # registers /health always + /metrics when enabled

    return app


def run_webhook() -> None:
    app = asyncio.run(build_web_app())
    web.run_app(app, host="0.0.0.0", port=8080)

# ─────────────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """
    Application entrypoint.

    Selects polling vs webhook based on BOT_WEBHOOK_URL:
    - Not set → polling (development)
    - Set     → webhook (staging/production)
    """
    # Step 1: Configure logging first (before any other imports use it)
    configure_logging()

    settings = get_settings()
    log.info(
        "bot_initialising",
        app_env=settings.app_env,
        mode="webhook" if settings.bot.webhook_url else "polling",
    )

    # Step 2: Initialise Sentry
    if settings.sentry.dsn:
        sentry_sdk.init(
            dsn=settings.sentry.dsn,
            traces_sample_rate=settings.sentry.traces_sample_rate,
            environment=settings.sentry.environment,
            integrations=[
                AioHttpIntegration(),
                SqlalchemyIntegration(),
            ],
            # Don't send debug info in production logs
            debug=settings.is_development,
        )
        log.info("sentry_initialised", environment=settings.sentry.environment)

    # Step 3: Launch
    if settings.bot.webhook_url:
        run_webhook()
    else:
        try:
            asyncio.run(run_polling())
        except KeyboardInterrupt:
            log.info("bot_interrupted_by_user")
            sys.exit(0)


if __name__ == "__main__":
    main()
