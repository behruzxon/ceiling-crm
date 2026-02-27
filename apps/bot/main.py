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
from apps.bot.handlers.admin.dashboard import router as dashboard_router
from apps.bot.handlers.admin.leads import router as admin_leads_router
from apps.bot.handlers.admin.media import router as media_router
from apps.bot.handlers.admin.pipeline import router as pipeline_router
from apps.bot.handlers.admin.reports import router as reports_router
from apps.bot.handlers.admin.scheduler import router as scheduler_router
from apps.bot.handlers.callbacks.lead_callbacks import router as lead_callbacks_router
from apps.bot.handlers.callbacks.payment_callbacks import router as payment_callbacks_router
from apps.bot.handlers.callbacks.pipeline_callbacks import router as pipeline_callbacks_router
from apps.bot.handlers.group.admin import router as group_admin_router
from apps.bot.handlers.group.admin_group_tracker import router as admin_group_tracker_router
from apps.bot.handlers.group.member_status import router as member_status_router
from apps.bot.handlers.group.messages import router as group_messages_router
from apps.bot.handlers.group.moderation import router as moderation_router
from apps.bot.handlers.group.welcome import router as welcome_router
from apps.bot.handlers.private.about import router as about_router
from apps.bot.handlers.private.ai_support import router as ai_support_router
from apps.bot.handlers.private.catalog import router as catalog_router
from apps.bot.handlers.private.lead_capture import router as lead_capture_router
from apps.bot.handlers.private.my_orders import router as my_orders_router
from apps.bot.handlers.private.operator import router as operator_router
from apps.bot.handlers.private.payment import router as payment_router
from apps.bot.handlers.private.order import router as order_router
from apps.bot.handlers.private.pricing import router as pricing_router
from apps.bot.handlers.private.promotions import router as promotions_router
from apps.bot.handlers.private.support import router as support_router
from apps.bot.middlewares.audit import AuditMiddleware
from apps.bot.middlewares.auth import AuthMiddleware
from apps.bot.middlewares.group_context import GroupContextMiddleware
from apps.bot.middlewares.locale import LocaleMiddleware
from apps.bot.middlewares.rate_limit import RateLimitMiddleware
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
    BotCommand(command="catalog", description="Shiftlar katalogi"),
    BotCommand(command="price",   description="Narxni hisoblash"),
    BotCommand(command="order",   description="Buyurtma berish"),
    BotCommand(command="help",    description="Yordam"),
    BotCommand(command="cancel",  description="Amalni bekor qilish"),
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
    dp.update.outer_middleware(LocaleMiddleware())
    dp.update.outer_middleware(GroupContextMiddleware())
    dp.update.outer_middleware(RateLimitMiddleware())
    dp.update.outer_middleware(AuditMiddleware())

    # ── Admin router (restricted access) ──────────────────────────────────
    admin_router = Router(name="admin")
    admin_router.include_routers(
        dashboard_router,
        admin_leads_router,
        pipeline_router,
        broadcasts_router,
        scheduler_router,
        reports_router,
        media_router,
    )

    # ── Callbacks router ───────────────────────────────────────────────────
    callbacks_router = Router(name="callbacks")
    callbacks_router.include_routers(
        lead_callbacks_router,
        pipeline_callbacks_router,
        payment_callbacks_router,
    )

    # ── Group router ───────────────────────────────────────────────────────
    group_router = Router(name="group")
    group_router.include_routers(
        group_admin_router,         # /admin command + gs: callbacks — must be first
        admin_group_tracker_router, # my_chat_member → upsert admin_groups (silent)
        member_status_router,
        welcome_router,             # join welcome + auto-delete
        moderation_router,          # link blocking + flood control
        group_messages_router,      # silent catch-all — must be last
    )

    # ── Private DM router ─────────────────────────────────────────────────
    private_router = Router(name="private")
    private_router.include_routers(
        support_router,      # /start /help /cancel — commands must win over any catch-all
        catalog_router,
        promotions_router,   # simple text+callback handler — no FSM state deps
        about_router,        # simple text+callback handler — owns open_catalog callback
        pricing_router,
        my_orders_router,    # must precede order_router (shares "📦" prefix text)
        payment_router,      # FSM — must precede lead_capture_router catch-all
        order_router,        # must precede lead_capture_router
        operator_router,     # must precede ai_support_router
        lead_capture_router,
        ai_support_router,  # free-text catch-all — commands already excluded by guard
    )

    # Mount all top-level routers into Dispatcher
    dp.include_routers(
        admin_router,
        callbacks_router,
        group_router,
        private_router,
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
            allowed_updates=dp.resolve_used_update_types(),
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

    if settings.prometheus_enabled:
        setup_prometheus(app)

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
