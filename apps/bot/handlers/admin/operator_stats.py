"""
apps.bot.handlers.admin.operator_stats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Full analytics suite for operators / managers.

Commands
--------
  /opstats [7|30]       — operator leaderboard + first-response time + funnel summary
  "📈 Manager statistika" — shortcut for /opstats 7
  /funnel [7|30]        — conversion funnel with stage counts and percentages
  /lead <id>            — lead card + last 10 action timeline
  /lead_<id>            — same, compact URL style (e.g. /lead_42)

RBAC: MANAGER | ADMIN | SUPERADMIN
Works in both DM and admin group chats.
Timezone: Asia/Tashkent for display.
"""

from __future__ import annotations

import re
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_analytics_service
from shared.constants.enums import UserRole

router = Router(name="admin:operator_stats")

_TZ = ZoneInfo("Asia/Tashkent")
_RBAC = RoleFilter(UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN)

# Emoji map for action_type → icon in timeline
_ACTION_EMOJI: dict[str, str] = {
    "hot": "🔥",
    "warm": "🟡",
    "cold": "❄️",
    "phone": "📞",
    "phone_viewed": "📞",
    "measurement": "📅",
    "measurement_set": "📐",
    "note": "📝",
    "block": "🚫",
    "lead_created": "🆕",
    "status_changed": "🔄",
    "order_done": "✅",
    "lead_assigned": "👔",
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _tashkent(dt: Any) -> str:
    """Format a timezone-aware datetime in Tashkent local time."""
    if dt is None:
        return "—"
    return dt.astimezone(_TZ).strftime("%d.%m %H:%M")


def _fmt_seconds(secs: float | None) -> str:
    """Convert float seconds to 'Xd Yson' human string."""
    if secs is None:
        return "—"
    total = int(secs)
    if total < 60:
        return f"{total} son"
    minutes, sec = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} daq {sec} son"
    hours, mins = divmod(minutes, 60)
    return f"{hours} soat {mins} daq"


def _pct(numerator: int, denominator: int) -> str:
    """Format a conversion percentage or '—' if denominator is zero."""
    if denominator == 0:
        return "—"
    return f"{numerator * 100 // denominator}%"


def _parse_days(text: str | None, default: int = 7) -> int:
    """Extract integer days from message text; clamp to [1, 30]."""
    if not text:
        return default
    parts = text.strip().split()
    if len(parts) >= 2:
        try:
            d = int(parts[-1])
            return max(1, min(d, 30))
        except ValueError:
            pass
    return default


def _parse_lead_id_from_text(text: str | None) -> int | None:
    """Extract lead id from '/lead 42' or '/lead_42' or '/lead_42@botname'."""
    if not text:
        return None
    # /lead_42 or /lead_42@botname
    m = re.search(r"/lead[_@\s]+(\d+)", text)
    if m:
        return int(m.group(1))
    return None


# ── /opstats ──────────────────────────────────────────────────────────────────


@router.message(Command("opstats"), _RBAC)
@router.message(F.text == "📈 Manager statistika", _RBAC)
async def cmd_opstats(message: Message, **data: object) -> None:
    """Operator leaderboard + first-response time + funnel summary."""
    days = _parse_days(message.text)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_lead_analytics_service(session)
        stats = await svc.opstats(days)

    leaderboard: list[dict] = stats["leaderboard"]
    resp: dict = stats["resp_stats"]
    funnel: dict = stats["funnel"]
    total_leads: int = funnel.get("total", 0)
    status_counts: dict = funnel.get("status_counts", {})
    stage_counts: dict = funnel.get("stage_counts", {})

    now_tz = message.date.astimezone(_TZ).strftime("%d.%m.%Y %H:%M") if message.date else "—"

    # ── Leaderboard section ──────────────────────────────────────────────────
    if leaderboard:
        lb_lines = [f"👥 <b>Top operatorlar (oxirgi {days} kun)</b>\n"]
        for rank, op in enumerate(leaderboard, start=1):
            uname = f"@{op['username']}" if op.get("username") else f"#{op['actor_user_id']}"
            lb_lines.append(
                f"{rank}. <b>{op['first_name']}</b> {uname}\n"
                f"   Lidlar: <b>{op['handled_leads']}</b>  "
                f"Amallar: {op['total_actions']}  "
                f"🔥 HOT: {op['hot_count']}"
            )
        leaderboard_text = "\n".join(lb_lines)
    else:
        leaderboard_text = "👥 <b>Top operatorlar</b>\n<i>Ma'lumot yo'q</i>"

    # ── First response section ───────────────────────────────────────────────
    avg_rt = _fmt_seconds(resp.get("avg_seconds"))
    med_rt = _fmt_seconds(resp.get("median_seconds"))
    responded = resp.get("responded_leads", 0)
    response_text = (
        f"⏱ <b>Birinchi javob vaqti</b>\n"
        f"   O'rtacha: <b>{avg_rt}</b>  |  Median: <b>{med_rt}</b>\n"
        f"   Javob berilgan lidlar: {responded}"
    )

    # ── Funnel summary section ───────────────────────────────────────────────
    hot_count = status_counts.get("hot", 0)
    meas_count = stage_counts.get("MEASUREMENT", 0)
    order_count = stage_counts.get("DEAL", 0) + stage_counts.get("QUOTE", 0)
    blocked_count = status_counts.get("blocked", 0)

    funnel_text = (
        f"📊 <b>Qisqacha voronka</b>\n"
        f"   Jami yaratildi: <b>{total_leads}</b>  |  "
        f"Bloklangan: {blocked_count}\n"
        f"   NEW→HOT: {_pct(hot_count, total_leads)}  "
        f"HOT→O'lchov: {_pct(meas_count, hot_count)}  "
        f"O'lchov→Buyurtma: {_pct(order_count, meas_count)}"
    )

    divider = "\n\n" + "─" * 32 + "\n\n"
    header = f"📈 <b>Operator statistika</b>\n" f"📅 Oxirgi {days} kun  |  {now_tz} (Tashkent)\n"
    await message.answer(
        header + divider + leaderboard_text + divider + response_text + divider + funnel_text
    )


# ── /funnel ───────────────────────────────────────────────────────────────────


@router.message(Command("funnel"), _RBAC)
async def cmd_funnel(message: Message, **data: object) -> None:
    """Conversion funnel with stage counts and percentages."""
    days = _parse_days(message.text)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_lead_analytics_service(session)
        data_funnel = await svc.funnel(days)

    total: int = data_funnel.get("total", 0)
    stage_counts: dict[str, int] = data_funnel.get("stage_counts", {})
    status_counts: dict[str, int] = data_funnel.get("status_counts", {})

    def _sc(stage: str) -> int:
        return stage_counts.get(stage, 0)

    def _ss(status: str) -> int:
        return status_counts.get(status, 0)

    new_cnt = _sc("NEW") + _sc("PACKAGE_SELECTED") + _sc("CONTACTED")
    warm_cnt = _ss("warm")
    hot_cnt = _ss("hot")
    meas_cnt = _sc("MEASUREMENT")
    order_cnt = _sc("DEAL") + _sc("QUOTE")
    done_cnt = _sc("COMPLETED") + _sc("INSTALLATION")
    blocked_cnt = _ss("blocked")

    lines = [
        f"📊 <b>Konversiya voronkasi</b>  (oxirgi {days} kun)\n",
        f"🆕 NEW         : <b>{new_cnt}</b>",
        f"🟡 WARM        : <b>{warm_cnt}</b>",
        f"🔥 HOT         : <b>{hot_cnt}</b>",
        f"📐 O'LCHOV     : <b>{meas_cnt}</b>",
        f"✅ BUYURTMA    : <b>{order_cnt}</b>",
        f"🏁 BAJARILDI   : <b>{done_cnt}</b>",
        f"🚫 BLOKLANGAN  : <b>{blocked_cnt}</b>",
        "",
        "📉 <b>Konversiya %</b>",
        f"   NEW → HOT          : {_pct(hot_cnt, total)}  ({hot_cnt}/{total})",
        f"   HOT → O'lchov      : {_pct(meas_cnt, hot_cnt)}  ({meas_cnt}/{hot_cnt})",
        f"   O'lchov → Buyurtma : {_pct(order_cnt, meas_cnt)}  ({order_cnt}/{meas_cnt})",
        "",
        f"📋 Jami yaratilgan lidlar: <b>{total}</b>",
    ]

    await message.answer("\n".join(lines))


# ── /lead and /lead_<id> ──────────────────────────────────────────────────────


@router.message(Command("lead"), _RBAC)
@router.message(F.text.regexp(r"^/lead_\d+"), _RBAC)
async def cmd_lead_card(message: Message, **data: object) -> None:
    """Show lead details + last 10 action timeline."""
    lead_id = _parse_lead_id_from_text(message.text)
    if lead_id is None:
        await message.answer(
            "❓ Lid raqamini kiriting:\n" "<code>/lead 42</code>  yoki  <code>/lead_42</code>"
        )
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_lead_analytics_service(session)
        lead, timeline = await svc.lead_card(lead_id)

    if lead is None:
        await message.answer(f"❌ Lid <b>#{lead_id}</b> topilmadi.")
        return

    # ── Lead card ────────────────────────────────────────────────────────────
    stage_val = lead.current_stage.value if lead.current_stage else "—"
    status_val = lead.lead_status or "—"
    created_str = _tashkent(lead.created_at)

    card_lines = [
        f"📋 <b>Lid #{lead.id}</b>",
        f"👤 {lead.name}",
        f"📱 <code>{lead.phone}</code>",
        f"📍 {lead.district}",
        f"🏷 {lead.category.value if lead.category else '—'}",
        f"📊 Bosqich: <b>{stage_val}</b>",
        f"⭐ Status: <b>{status_val}</b>",
        f"📅 Yaratildi: {created_str} (Tashkent)",
    ]
    if lead.assigned_manager_id:
        card_lines.append(f"👔 Manager ID: {lead.assigned_manager_id}")
    if lead.notes:
        card_lines.append(f"📝 Izoh: {lead.notes}")

    # ── Timeline ─────────────────────────────────────────────────────────────
    if timeline:
        timeline_lines = ["\n📜 <b>Oxirgi amallar:</b>"]
        for row in timeline:
            ts = _tashkent(row.get("created_at"))
            atype = row.get("action_type", "?")
            icon = _ACTION_EMOJI.get(atype, "▪️")
            fname = row.get("first_name") or ""
            uname = row.get("username")
            actor = f"@{uname}" if uname else (fname or f"#{row.get('actor_user_id', '?')}")
            timeline_lines.append(f"  {ts}  {icon} <code>{atype}</code>  {actor}")
        card_lines.extend(timeline_lines)
    else:
        card_lines.append("\n<i>Hali hech qanday amal yo'q</i>")

    await message.answer("\n".join(card_lines))
