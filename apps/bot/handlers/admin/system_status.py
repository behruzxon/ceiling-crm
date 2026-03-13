"""
Admin /system_status command.
Shows database, Redis, OpenAI connectivity and uptime diagnostics.
"""
from __future__ import annotations

import time
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)

router = Router(name="admin:system_status")

_BOOT_TIME = time.monotonic()


def _fmt_uptime(seconds: float) -> str:
    """Format seconds into human-readable uptime."""
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts: list[str] = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


@router.message(Command("system_status"), RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_system_status(message: Message, **data: Any) -> None:
    """Show system diagnostics: DB, Redis, OpenAI, uptime."""
    lines: list[str] = ["🖥 <b>System Status</b>\n"]

    # ── Uptime ───────────────────────────────────────────────────────
    uptime_sec = time.monotonic() - _BOOT_TIME
    lines.append(f"⏱ Uptime: <b>{_fmt_uptime(uptime_sec)}</b>")

    # ── Database ─────────────────────────────────────────────────────
    db_status = "❌ error"
    try:
        from infrastructure.database.session import get_session_factory
        import sqlalchemy as sa

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(sa.text("SELECT 1"))
        db_status = "✅ ok"
    except Exception as exc:
        db_status = f"❌ {exc.__class__.__name__}"
    lines.append(f"🗄 Database: <b>{db_status}</b>")

    # ── Redis ────────────────────────────────────────────────────────
    redis_status = "❌ error"
    try:
        from infrastructure.cache.client import get_redis

        ok = await get_redis().ping()
        redis_status = "✅ ok" if ok else "❌ ping failed"
    except Exception as exc:
        redis_status = f"❌ {exc.__class__.__name__}"
    lines.append(f"🔴 Redis: <b>{redis_status}</b>")

    # ── OpenAI ───────────────────────────────────────────────────────
    openai_status = "❌ error"
    try:
        import httpx
        from shared.config import get_settings

        settings = get_settings()
        api_key = (
            settings.ai.api_key.get_secret_value()
            if settings.ai.api_key
            else settings.openai.api_key.get_secret_value()
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                openai_status = "✅ ok"
            else:
                openai_status = f"⚠️ HTTP {resp.status_code}"
    except Exception as exc:
        openai_status = f"❌ {exc.__class__.__name__}"
    lines.append(f"🤖 OpenAI: <b>{openai_status}</b>")

    # ── System errors (last 24h) ─────────────────────────────────────
    try:
        from datetime import datetime, timedelta, timezone

        import sqlalchemy as sa

        from infrastructure.database.models.system_error import SystemErrorModel
        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                sa.select(sa.func.count(SystemErrorModel.id)).where(
                    SystemErrorModel.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
                )
            )
            err_count = result.scalar() or 0
        lines.append(f"⚠️ Errors (24h): <b>{err_count}</b>")
    except Exception:
        pass

    await message.answer("\n".join(lines))
