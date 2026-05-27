"""
infrastructure.database.session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async SQLAlchemy engine, session factory, and dependency helpers.

Provides:
- `engine`         — AsyncEngine singleton
- `AsyncSessionFactory` — scoped async session factory
- `get_session()`  — async context manager for unit-of-work sessions
- `get_db()`       — FastAPI / aiogram dependency injection helper

Connection pooling is configured from DatabaseSettings.  All queries
run through asyncpg.  The sync engine is available for Alembic only.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Declarative Base — all ORM models inherit from this
# ─────────────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for all ORM models.

    All tables are automatically created with:
    - UTC timestamps via server_default
    - Consistent naming conventions
    """

    # Naming convention ensures Alembic-generated constraint names are stable
    # across DB engines and migration runs.
    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """Serialise model to dict (shallow, no relationships)."""
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}


# ─────────────────────────────────────────────────────────────────────────────
# Engine & Session Factory
# ─────────────────────────────────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_engine() -> AsyncEngine:
    """Build and configure the async SQLAlchemy engine."""
    settings = get_settings()
    db = settings.db

    engine = create_async_engine(
        db.async_url,
        echo=db.echo,
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout,
        pool_pre_ping=True,          # detect stale connections
        pool_recycle=3600,           # recycle connections after 1 hour
        connect_args={
            # asyncpg-specific: disable JIT for predictable query plans
            "server_settings": {"jit": "off"},
            "command_timeout": 60,
        },
    )

    log.info(
        "database_engine_created",
        host=db.host,
        port=db.port,
        database=db.db,
        pool_size=db.pool_size,
    )
    return engine


def get_engine() -> AsyncEngine:
    """Return the AsyncEngine singleton, creating it if necessary."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,   # objects remain accessible after commit
            autoflush=False,          # explicit flush control
            autocommit=False,
        )
    return _session_factory


# ─────────────────────────────────────────────────────────────────────────────
# Session context managers
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager providing a database session.

    Handles commit on success and rollback on exception.
    Use this for service-layer operations.

    Example:
        async with get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_readonly_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for read-only queries.

    Never commits.  Suitable for analytics and reporting queries
    that should not accidentally modify data.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency (for future web admin panel)
# ─────────────────────────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    Usage in a FastAPI route:
        @router.get("/leads")
        async def list_leads(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle helpers
# ─────────────────────────────────────────────────────────────────────────────


async def connect_database() -> None:
    """
    Initialise the database connection pool.
    Call once at application startup.
    Verifies connectivity with a lightweight SELECT 1.
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("database_connected", url=get_settings().db.host)
    except Exception as exc:
        log.error("database_connection_failed", error=str(exc), exc_info=True)
        raise


async def disconnect_database() -> None:
    """
    Dispose the connection pool.
    Call on application shutdown to release all connections gracefully.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        log.info("database_disconnected")
        _engine = None
        _session_factory = None


async def check_database_health() -> dict[str, Any]:
    """
    Health check for monitoring endpoints.

    Returns:
        dict with status, pool stats, and latency.
    """
    import time

    engine = get_engine()
    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (time.monotonic() - start) * 1000
        pool = engine.pool
        return {
            "status": "ok",
            "latency_ms": round(latency_ms, 2),
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
