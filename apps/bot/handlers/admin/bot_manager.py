"""
apps.bot.handlers.admin.bot_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SUPERADMIN-only bot management panel.

Commands:
  /bots              -- list all tenant bots with runtime status

Callbacks (botmgr: prefix):
  botmgr:detail:{id} -- detailed status of one bot
  botmgr:restart:{id}-- restart one bot
  botmgr:stop:{id}   -- stop one bot
  botmgr:start:{id}  -- start a stopped/failed bot
  botmgr:resync      -- reload all bots from DB
  botmgr:back        -- return to list view

RBAC: SUPERADMIN only
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.filters.role import RoleFilter
from core.services.bot_registry import BotStatus, get_bot_registry
from infrastructure.database.session import get_session_factory
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:bot_manager")

_SUPERADMIN = (UserRole.SUPERADMIN,)

_STATUS_ICONS = {
    BotStatus.STARTING.value: "[...]",
    BotStatus.RUNNING.value:  "[OK]",
    BotStatus.FAILED.value:   "[ERR]",
    BotStatus.STOPPED.value:  "[OFF]",
    BotStatus.PAUSED.value:   "[PAUSE]",
}


# ── Formatting ───────────────────────────────────────────────────────────


def _format_uptime(started: datetime | None) -> str:
    if not started:
        return "--"
    delta = datetime.now(timezone.utc) - started
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _format_ago(dt: datetime | None) -> str:
    if not dt:
        return "--"
    delta = datetime.now(timezone.utc) - dt
    mins = int(delta.total_seconds()) // 60
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h {mins % 60}m ago"
    return f"{hours // 24}d ago"


def _format_bot_list(statuses: list[dict]) -> str:
    if not statuses:
        return "Bot Manager\n=============================\nNo tenant bots configured."

    lines = [f"Bot Manager ({len(statuses)} bots)", "============================="]

    for i, s in enumerate(statuses, 1):
        icon = _STATUS_ICONS.get(s["status"], "[?]")
        username = f'@{s["bot_username"]}' if s["bot_username"] else s["tenant_name"]
        lines.append(f"{i}. {username} {icon} T:{s['tenant_id']}")

        if s["status"] == BotStatus.RUNNING.value:
            uptime = _format_uptime(s.get("last_started"))
            lines.append(f"   bot_id: {s['bot_id']} | uptime: {uptime}")
        elif s["status"] == BotStatus.FAILED.value:
            err = s.get("last_error") or "unknown"
            ago = _format_ago(s.get("last_error_at"))
            lines.append(f"   Err: {err[:50]} | {ago}")
        elif s["status"] == BotStatus.PAUSED.value:
            lines.append("   Tenant deactivated")
        elif s["status"] == BotStatus.STOPPED.value:
            lines.append("   Administratively stopped")

    lines.append("=============================")
    return "\n".join(lines)


def _format_bot_detail(status_dict: dict) -> str:
    s = status_dict
    username = f'@{s["bot_username"]}' if s["bot_username"] else s["tenant_name"]
    started_str = s["last_started"].strftime("%Y-%m-%d %H:%M UTC") if s.get("last_started") else "--"
    uptime = _format_uptime(s.get("last_started")) if s["status"] == BotStatus.RUNNING.value else "--"

    lines = [
        f"Bot: {username}",
        "=============================",
        f"Tenant ID:   {s['tenant_id']}",
        f"Bot ID:      {s['bot_id'] or '--'}",
        f"Status:      {s['status']}",
        f"Last start:  {started_str}",
        f"Uptime:      {uptime}",
        f"Errors:      {s['error_count']}",
        f"Last error:  {s.get('last_error') or '--'}",
    ]
    return "\n".join(lines)


# ── Keyboards ────────────────────────────────────────────────────────────


def _list_keyboard(statuses: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for s in statuses:
        tid = s["tenant_id"]
        label = f'@{s["bot_username"]}' if s["bot_username"] else f'T:{tid}'
        buttons.append([InlineKeyboardButton(
            text=f"{label} {_STATUS_ICONS.get(s['status'], '')}",
            callback_data=f"botmgr:detail:{tid}",
        )])
    buttons.append([InlineKeyboardButton(
        text="Resync from DB",
        callback_data="botmgr:resync",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _detail_keyboard(tenant_id: int, status: str) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []

    if status == BotStatus.RUNNING.value:
        buttons.append(InlineKeyboardButton(
            text="Restart", callback_data=f"botmgr:restart:{tenant_id}",
        ))
        buttons.append(InlineKeyboardButton(
            text="Stop", callback_data=f"botmgr:stop:{tenant_id}",
        ))
    elif status in (BotStatus.STOPPED.value, BotStatus.FAILED.value):
        buttons.append(InlineKeyboardButton(
            text="Start", callback_data=f"botmgr:start:{tenant_id}",
        ))

    buttons.append(InlineKeyboardButton(
        text="<< Back", callback_data="botmgr:back",
    ))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# ── Handlers ─────────────────────────────────────────────────────────────


@router.message(Command("bots"), RoleFilter(*_SUPERADMIN))
async def cmd_bots(message: Message, **data: object) -> None:
    """List all tenant bots with runtime status."""
    registry = get_bot_registry()
    statuses = registry.list_status()
    text = _format_bot_list(statuses)
    await message.answer(text, reply_markup=_list_keyboard(statuses))


@router.callback_query(F.data == "botmgr:back", RoleFilter(*_SUPERADMIN))
async def cb_back(callback: CallbackQuery, **data: object) -> None:
    """Return to bot list view."""
    await callback.answer()
    registry = get_bot_registry()
    statuses = registry.list_status()
    text = _format_bot_list(statuses)
    await callback.message.edit_text(text, reply_markup=_list_keyboard(statuses))  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("botmgr:detail:"), RoleFilter(*_SUPERADMIN))
async def cb_detail(callback: CallbackQuery, **data: object) -> None:
    """Show detailed status of one bot."""
    await callback.answer()
    tenant_id = int((callback.data or "").split(":")[-1])

    registry = get_bot_registry()
    # Find the status dict for this tenant
    statuses = registry.list_status()
    target = next((s for s in statuses if s["tenant_id"] == tenant_id), None)

    if target is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found in registry.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="botmgr:back"),
            ]]),
        )
        return

    text = _format_bot_detail(target)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_detail_keyboard(tenant_id, target["status"]),
    )


@router.callback_query(F.data == "botmgr:resync", RoleFilter(*_SUPERADMIN))
async def cb_resync(callback: CallbackQuery, **data: object) -> None:
    """Resync all bots from database."""
    await callback.answer("Resyncing...")
    log.info("bot_resync_requested", by_user=callback.from_user.id)

    registry = get_bot_registry()
    factory = get_session_factory()
    async with factory() as session:
        summary = await registry.resync_from_db(session)

    statuses = registry.list_status()
    header = (
        f"Resync complete: +{summary['added']} added, "
        f"-{summary['removed']} removed, "
        f"~{summary['restarted']} restarted, "
        f"={summary['unchanged']} unchanged\n\n"
    )
    text = header + _format_bot_list(statuses)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_list_keyboard(statuses),
    )


@router.callback_query(F.data.startswith("botmgr:restart:"), RoleFilter(*_SUPERADMIN))
async def cb_restart(callback: CallbackQuery, **data: object) -> None:
    """Restart a specific tenant bot."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Restarting...")
    log.info("bot_restart_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    registry = get_bot_registry()
    factory = get_session_factory()
    async with factory() as session:
        new_status = await registry.restart_bot(tenant_id, session)

    # Show updated detail view
    statuses = registry.list_status()
    target = next((s for s in statuses if s["tenant_id"] == tenant_id), None)
    if target:
        text = f"Restart result: {new_status.value}\n\n{_format_bot_detail(target)}"
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=_detail_keyboard(tenant_id, target["status"]),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Restart result: {new_status.value}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="botmgr:back"),
            ]]),
        )


@router.callback_query(F.data.startswith("botmgr:stop:"), RoleFilter(*_SUPERADMIN))
async def cb_stop(callback: CallbackQuery, **data: object) -> None:
    """Stop a specific tenant bot."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Stopping...")
    log.info("bot_stop_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    registry = get_bot_registry()
    ok = await registry.stop_bot(tenant_id)

    statuses = registry.list_status()
    target = next((s for s in statuses if s["tenant_id"] == tenant_id), None)
    if target:
        result = "Stopped" if ok else "Not found"
        text = f"Stop result: {result}\n\n{_format_bot_detail(target)}"
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=_detail_keyboard(tenant_id, target["status"]),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="botmgr:back"),
            ]]),
        )


@router.callback_query(F.data.startswith("botmgr:start:"), RoleFilter(*_SUPERADMIN))
async def cb_start(callback: CallbackQuery, **data: object) -> None:
    """Start a stopped or failed tenant bot."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Starting...")
    log.info("bot_start_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    registry = get_bot_registry()
    factory = get_session_factory()
    async with factory() as session:
        new_status = await registry.start_bot(tenant_id, session)

    statuses = registry.list_status()
    target = next((s for s in statuses if s["tenant_id"] == tenant_id), None)
    if target:
        text = f"Start result: {new_status.value}\n\n{_format_bot_detail(target)}"
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=_detail_keyboard(tenant_id, target["status"]),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Start result: {new_status.value}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="botmgr:back"),
            ]]),
        )
