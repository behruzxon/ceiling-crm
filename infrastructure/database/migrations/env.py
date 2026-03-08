"""
Alembic migration environment.

Supports both online (direct DB) and offline (SQL script generation) modes.
Uses async SQLAlchemy engine from infrastructure/database/session.py.
DB URL is loaded from Pydantic Settings — never hardcoded here.

Run migrations:
    alembic upgrade head               # apply all pending migrations
    alembic downgrade -1               # roll back last migration
    alembic revision --autogenerate -m "add_column_x"  # generate new migration
    alembic history --verbose          # show migration history
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Import all models so Alembic can detect schema changes ────────────────
# IMPORTANT: add each new model import here when creating it.
from infrastructure.database.session import Base  # noqa: F401 — Base metadata
from infrastructure.database.models.user import UserModel  # noqa: F401
from infrastructure.database.models.lead import LeadModel  # noqa: F401
from infrastructure.database.models.group import GroupModel  # noqa: F401
from infrastructure.database.models.pipeline_stage import PipelineStageModel  # noqa: F401
from infrastructure.database.models.audit_log import AuditLogModel  # noqa: F401
from infrastructure.database.models.quote import QuoteModel  # noqa: F401
from infrastructure.database.models.appointment import AppointmentModel  # noqa: F401
from infrastructure.database.models.broadcast import BroadcastModel  # noqa: F401
from infrastructure.database.models.ai_memory import AiMemoryModel  # noqa: F401
from infrastructure.database.models.ai_conversation import AiConversationModel  # noqa: F401
from infrastructure.database.models.group_settings import GroupSettingsModel  # noqa: F401
from infrastructure.database.models.payment import PaymentModel  # noqa: F401
from infrastructure.database.models.warranty import WarrantyModel  # noqa: F401
from infrastructure.database.models.admin_group import AdminGroupModel  # noqa: F401
from infrastructure.database.models.blocked_chat import BlockedChatModel  # noqa: F401
from infrastructure.database.models.group_join_event import GroupJoinEventModel  # noqa: F401
from infrastructure.database.models.lead_action import LeadActionModel  # noqa: F401
from infrastructure.database.models.tenant import TenantModel  # noqa: F401
from infrastructure.database.models.subscription_payment import SubscriptionPaymentModel  # noqa: F401
from infrastructure.database.models.ai_knowledge import TenantAiKnowledgeModel  # noqa: F401

from shared.config import get_settings

# ── Alembic Config ─────────────────────────────────────────────────────────
config = context.config
fileConfig(config.config_file_name)  # configure stdlib logging from alembic.ini
target_metadata = Base.metadata


def get_async_url() -> str:
    """Async DSN (asyncpg) for online migrations."""
    return get_settings().db.async_url


def get_sync_url() -> str:
    """Sync DSN (psycopg2) for offline SQL script generation."""
    return get_settings().db.sync_url


# ── Offline mode (generates SQL script, no live DB required) ──────────────
def run_migrations_offline() -> None:
    """
    Generate a SQL migration script without connecting to the database.
    Uses sync psycopg2 URL since no actual connection is made.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (applies migrations directly to DB) ───────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async asyncpg engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_async_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ── Dispatcher ────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
