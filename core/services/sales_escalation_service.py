"""
core.services.sales_escalation_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Real-time escalation of HOT leads to the tenant's admin group.

Called fire-and-forget from AI chat handlers after every LLM reply.
Uses Redis NX for 30-minute cooldown per user per tenant bot.

Public API
----------
  should_escalate(...)           — pure function, 6 trigger rules
  check_escalation_cooldown(...) — Redis NX, returns True if lock acquired
  send_escalation(...)           — async, sends card to admin group via tenant bot
"""
from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.logging import get_logger

log = get_logger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────

_SCORE_HIGH = 50
_SCORE_MODERATE = 30
_CONFIDENCE_THRESHOLD = 0.7
_BUYING_INTENTS: frozenset[str] = frozenset({"order", "measurement"})
_COMMERCIAL_INTENTS: frozenset[str] = frozenset({"price", "consultation"})


# ── Result dataclass ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    """Result of should_escalate() evaluation."""

    should: bool
    reason: str


# ── Trigger evaluation (pure function) ─────────────────────────────────────


def should_escalate(
    *,
    score: int,
    intent: str,
    lead_temperature: str | None,
    closing_confidence: float | None,
    phone_captured: bool,
    has_area: bool,
) -> EscalationDecision:
    """Evaluate 6 escalation trigger rules. Returns decision with reason.

    Any single rule firing is sufficient to trigger escalation.
    Rules are checked in priority order; first match wins.
    """
    if lead_temperature == "hot":
        return EscalationDecision(True, "AI classified as HOT")

    if score >= _SCORE_HIGH:
        return EscalationDecision(True, f"Lead score {score} >= {_SCORE_HIGH}")

    if closing_confidence is not None and closing_confidence >= _CONFIDENCE_THRESHOLD:
        return EscalationDecision(
            True, f"Closing confidence {closing_confidence:.0%}",
        )

    if phone_captured and has_area:
        return EscalationDecision(True, "Phone + area shared")

    if intent in _BUYING_INTENTS:
        return EscalationDecision(True, f"Buying intent: {intent}")

    if score >= _SCORE_MODERATE and intent in _COMMERCIAL_INTENTS:
        return EscalationDecision(
            True, f"Commercial intent + score {score}",
        )

    return EscalationDecision(False, "")


# ── Cooldown (Redis NX) ───────────────────────────────────────────────────


async def check_escalation_cooldown(
    user_id: int, *, bot_id: int | None = None,
) -> bool:
    """Return True if the cooldown lock was acquired (= no recent escalation).

    Uses SET NX so the key is only created if it does not yet exist.
    """
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        ok = await get_redis().set(
            CacheKeys.escalation_last(user_id, bot_id=bot_id),
            "1",
            ttl=CacheTTL.ESCALATION_COOLDOWN,
            nx=True,
        )
        return bool(ok)
    except Exception:
        # Redis unavailable → allow the escalation (fail-open)
        return True


# ── Card builder ───────────────────────────────────────────────────────────

_TEMP_ICONS: dict[str, str] = {
    "hot": "HOT",
    "warm": "WARM",
    "cold": "COLD",
}


def build_escalation_card(
    *,
    user_id: int,
    name: str | None,
    username: str | None,
    score: int,
    intent: str,
    lead_temperature: str | None,
    closing_confidence: float | None,
    reason: str,
    last_message: str,
    lead_id: int | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build the escalation notification text + inline keyboard.

    Returns (text, keyboard).
    """
    temp_icon = _TEMP_ICONS.get(lead_temperature or "", "?")
    cc_str = f"{closing_confidence:.0%}" if closing_confidence is not None else "--"
    user_line = name or "Noma'lum"
    tg_line = f"@{username}" if username else f"ID: {user_id}"

    lines = [
        f"HOT LEAD — {temp_icon}",
        "",
        f"Foydalanuvchi: {user_line}",
        f"Telegram: {tg_line}",
        "",
        f"Holat: {temp_icon} | Ball: {score}",
        f"Ishonch: {cc_str}",
        f"Intent: {intent}",
        "",
        f"Sabab: {reason}",
    ]

    if last_message:
        truncated = last_message[:150]
        lines.append("")
        lines.append(f'Oxirgi xabar: "{truncated}"')

    text = "\n".join(lines)

    # Quick-action keyboard
    buttons: list[list[InlineKeyboardButton]] = []
    if lead_id:
        buttons.append([InlineKeyboardButton(
            text="Kanban'da ochish",
            callback_data=f"kanban:lead:{lead_id}:new",
        )])
    buttons.append([
        InlineKeyboardButton(
            text="Bog'lanish",
            callback_data=f"lead:{lead_id or 0}:status:contacted",
        ),
        InlineKeyboardButton(
            text="O'lchov",
            callback_data=f"lead:{lead_id or 0}:status:measurement",
        ),
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Send escalation ───────────────────────────────────────────────────────


async def send_escalation(
    bot: Bot,
    admin_group_id: int,
    user_id: int,
    *,
    score: int,
    intent: str,
    lead_temperature: str | None,
    closing_confidence: float | None,
    name: str | None,
    username: str | None,
    last_message: str,
    reason: str,
    lead_id: int | None = None,
) -> None:
    """Send escalation card to admin group. Never raises."""
    try:
        text, kb = build_escalation_card(
            user_id=user_id,
            name=name,
            username=username,
            score=score,
            intent=intent,
            lead_temperature=lead_temperature,
            closing_confidence=closing_confidence,
            reason=reason,
            last_message=last_message,
            lead_id=lead_id,
        )
        await bot.send_message(admin_group_id, text, reply_markup=kb)
        log.info(
            "escalation_sent",
            user_id=user_id,
            admin_group_id=admin_group_id,
            reason=reason,
            score=score,
            lead_temperature=lead_temperature,
        )
    except Exception:
        log.warning(
            "escalation_send_failed",
            user_id=user_id,
            admin_group_id=admin_group_id,
        )
