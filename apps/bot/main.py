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

from apps.bot.handlers.admin.billing import router as billing_router
from apps.bot.handlers.admin.bot_manager import router as bot_manager_router
from apps.bot.handlers.admin.broadcasts import router as broadcasts_router
from apps.bot.handlers.admin.analytics import router as analytics_router
from apps.bot.handlers.admin.dashboard import router as dashboard_router
from apps.bot.handlers.admin.lead_status import router as lead_status_router
from apps.bot.handlers.admin.leads import router as admin_leads_router
from apps.bot.handlers.admin.media import router as media_router
from apps.bot.handlers.admin.operator_stats import router as operator_stats_router
from apps.bot.handlers.admin.pipeline import router as pipeline_router
from apps.bot.handlers.admin.radar import router as radar_router
from apps.bot.handlers.admin.reports import router as reports_router
from apps.bot.handlers.admin.stats import router as stats_router
from apps.bot.handlers.admin.scheduler import router as scheduler_router
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
from apps.bot.handlers.private.auto_onboarding import router as auto_onboarding_router
from apps.bot.handlers.private.menu_builder import router as menu_builder_router
from apps.bot.handlers.private.onboarding import router as onboarding_router
from apps.bot.handlers.private.owner_dashboard import router as owner_dashboard_router
from apps.bot.handlers.private.knowledge import router as knowledge_router
from apps.bot.handlers.private.tenant_bot import router as tenant_bot_router
from apps.bot.handlers.private.support import router as support_router
from apps.bot.tasks import daily_report, inactive_cta
from apps.bot.middlewares.audit import AuditMiddleware
from apps.bot.middlewares.auth import AuthMiddleware
from apps.bot.middlewares.group_context import GroupContextMiddleware
from apps.bot.middlewares.group_menu_injector import GroupMenuInjectorMiddleware
from apps.bot.middlewares.locale import LocaleMiddleware
from apps.bot.middlewares.rate_limit import RateLimitMiddleware
from apps.bot.middlewares.tenant_context import TenantContextMiddleware
from core.services.bot_registry import get_bot_registry
from infrastructure.cache.client import connect_redis, disconnect_redis, get_sessions_redis
from infrastructure.database.session import connect_database, disconnect_database, get_session_factory
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
    if get_settings().bot.runtime_mode == "multi":
        dp.update.outer_middleware(TenantContextMiddleware())
    dp.update.outer_middleware(LocaleMiddleware())
    dp.update.outer_middleware(GroupContextMiddleware())
    dp.update.outer_middleware(RateLimitMiddleware())
    dp.update.outer_middleware(AuditMiddleware())
    dp.message.outer_middleware(GroupMenuInjectorMiddleware())  # inject selective ReplyKeyboard in groups

    # ── Admin router (restricted access) ──────────────────────────────────
    admin_router = Router(name="admin")
    admin_router.include_routers(
        dashboard_router,
        admin_leads_router,
        pipeline_router,
        radar_router,
        analytics_router,
        broadcasts_router,
        scheduler_router,
        operator_stats_router,
        reports_router,
        media_router,
        stats_router,          # /stats + stats:period:* callbacks
        bot_manager_router,    # /bots + botmgr:* — SUPERADMIN bot management
        billing_router,        # /tenants + billing:* — SUPERADMIN billing management
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
        auto_onboarding_router,   # SaaS auto-onboarding FSM — before catch-all
        onboarding_router,        # SaaS tenant onboarding wizard — before catch-all
        menu_builder_router,      # SaaS menu builder — before catch-all
        owner_dashboard_router,   # SaaS owner CRM dashboard — before catch-all
        knowledge_router,         # SaaS AI knowledge base manager — before catch-all
        tenant_bot_router,        # SaaS tenant bot connection manager — before catch-all
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


async def on_startup(bot: Bot) -> None:
    """
    Called once when the bot application starts.
    Initialises all external connections and registers bot commands.
    """
    log.info("bot_startup_begin")

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
# Multi-bot lifecycle (runtime_mode = "multi")
# ─────────────────────────────────────────────────────────────────────────────

_multi_infra_connected = False  # ensure DB/Redis connect only once across bots


async def on_startup_multi(bot: Bot) -> None:
    """Called once per bot when multi-bot runtime starts."""
    global _multi_infra_connected

    if not _multi_infra_connected:
        await connect_database()
        await connect_redis()
        _multi_infra_connected = True

    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())

    settings = get_settings()
    if settings.bot.webhook_url:
        await bot.set_webhook(
            url=f"{settings.bot.webhook_url}/webhook/{bot.id}",
            secret_token=settings.bot.webhook_secret.get_secret_value()
            if settings.bot.webhook_secret
            else None,
            drop_pending_updates=True,
            max_connections=settings.bot.max_connections,
        )
        log.info("multi_webhook_registered", bot_id=bot.id, url=f"{settings.bot.webhook_url}/webhook/{bot.id}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)

    registry = get_bot_registry()
    config = registry.get_config_by_bot_id(bot.id)
    tenant_label = config.bot_username if config else bot.id
    log.info("multi_bot_started", bot_id=bot.id, tenant=tenant_label)

    # Background tasks run on the first registered bot only (Phase 1)
    bots = registry.all_bots()
    if bots and bots[0].id == bot.id:
        daily_report.start(bot)
        inactive_cta.start(bot)


async def on_shutdown_multi(bot: Bot) -> None:
    """Called once per bot during multi-bot shutdown."""
    registry = get_bot_registry()
    bots = registry.all_bots()

    # Stop background tasks (only first bot started them)
    if bots and bots[0].id == bot.id:
        daily_report.stop()
        inactive_cta.stop()

    await bot.session.close()

    # Disconnect infra on the last bot shutdown
    if bots and bots[-1].id == bot.id:
        await disconnect_database()
        await disconnect_redis()
        log.info("multi_bot_shutdown_complete")


async def run_polling_multi() -> None:
    """
    Multi-bot polling mode.

    Loads all active tenant bots from the database and starts polling
    for all of them on a shared Dispatcher.
    """
    # Connect DB early to load tenant bots
    await connect_database()

    registry = get_bot_registry()
    factory = get_session_factory()
    async with factory() as session:
        await registry.load_from_db(session)

    bots = registry.all_bots()
    if not bots:
        log.error("no_active_tenant_bots_found")
        await disconnect_database()
        return

    storage = await create_storage()
    dp = build_dispatcher(storage)

    dp.startup.register(on_startup_multi)
    dp.shutdown.register(on_shutdown_multi)

    log.info("starting_multi_bot_polling", bot_count=len(bots))
    try:
        await dp.start_polling(
            *bots,
            allowed_updates=[
                "message",
                "callback_query",
                "chat_member",
                "my_chat_member",
            ],
            handle_signals=True,
        )
    finally:
        log.info("multi_bot_polling_stopped")


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

    When ``BOT_RUNTIME_MODE=multi``, loads all tenant bots from the
    database and polls for all of them on a shared Dispatcher.
    """
    settings = get_settings()
    if settings.bot.runtime_mode == "multi":
        await run_polling_multi()
        return

    # ── Single-bot mode (default) ────────────────────────────────────────
    bot = create_bot()
    storage = await create_storage()
    dp = build_dispatcher(storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start background HTTP server for payment webhooks (if any provider configured)
    webhook_runner = None
    if settings.click.is_configured or settings.payme.is_configured:
        webhook_app = web.Application()
        _register_payment_webhooks(webhook_app, settings)
        if settings.prometheus_enabled:
            setup_prometheus(webhook_app)
        webhook_runner = web.AppRunner(webhook_app)
        await webhook_runner.setup()
        site = web.TCPSite(webhook_runner, "0.0.0.0", 8080)
        await site.start()
        log.info("payment_webhook_server_started", port=8080)

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
        if webhook_runner:
            await webhook_runner.cleanup()
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
    app = web.Application()

    if settings.bot.runtime_mode == "multi":
        # ── Multi-bot webhook ────────────────────────────────────────────
        await connect_database()

        registry = get_bot_registry()
        factory = get_session_factory()
        async with factory() as session:
            await registry.load_from_db(session)

        storage = await create_storage()
        dp = build_dispatcher(storage)
        dp.startup.register(on_startup_multi)
        dp.shutdown.register(on_shutdown_multi)

        secret = (
            settings.bot.webhook_secret.get_secret_value()
            if settings.bot.webhook_secret
            else None
        )

        for bot in registry.all_bots():
            SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=secret,
            ).register(app, path=f"/webhook/{bot.id}")

        setup_application(app, dp, bot=registry.all_bots()[0])
        log.info("multi_bot_webhook_configured", bot_count=registry.bot_count)
    else:
        # ── Single-bot webhook (default) ─────────────────────────────────
        bot, dp = await create_bot_async()

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

    if settings.prometheus_enabled:
        setup_prometheus(app)

    # ── Payment provider webhooks ─────────────────────────────────────
    _register_payment_webhooks(app, settings)

    return app


def _register_payment_webhooks(app: web.Application, settings: Any = None) -> None:
    """Conditionally register Click.uz and Payme.uz webhook routes."""
    if settings is None:
        settings = get_settings()
    if settings.click.is_configured:
        from apps.bot.webhooks.click_webhook import setup_click_routes
        setup_click_routes(app)
        log.info("click_webhook_routes_registered")
    if settings.payme.is_configured:
        from apps.bot.webhooks.payme_webhook import setup_payme_routes
        setup_payme_routes(app)
        log.info("payme_webhook_routes_registered")


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
        runtime_mode=settings.bot.runtime_mode,
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
