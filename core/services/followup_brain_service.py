"""
core.services.followup_brain_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Intelligent follow-up decision engine for leads.

Upgrades simple delay-based follow-up into context-aware decisions:
what type of follow-up to send, when, and whether to skip entirely.

Follow-up types
---------------
  price_reminder       — remind about pricing they asked about
  catalog_nudge        — nudge with catalog / design options
  measurement_push     — push for free measurement booking
  soft_reactivation    — gentle re-engagement after silence
  manager_call_offer   — offer human manager intervention
  budget_option_offer  — suggest cheaper alternative for price objectors

Usage::

    from core.services.followup_brain_service import decide_follow_up

    decision = decide_follow_up(
        score=65,
        deal_probability_percent=72,
        buyer_type="fast_buyer",
        decision_stage="close_ready",
        engagement_trend="warming_up",
        phone_captured=True,
    )
    # decision.follow_up_type == "measurement_push"
    # decision.follow_up_delay_minutes == 20
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FollowUpDecision:
    """Structured follow-up decision for a lead."""

    should_follow_up: bool
    """Whether to schedule a follow-up at all."""

    follow_up_delay_minutes: int | None
    """Minutes until follow-up, or None if skipping."""

    follow_up_type: str
    """One of: price_reminder | catalog_nudge | measurement_push |
    soft_reactivation | manager_call_offer | budget_option_offer | none."""

    follow_up_message: str
    """Uzbek-language follow-up message text. Empty when skipping."""

    follow_up_reason: str
    """Human-readable reason for the decision."""

    skip_reason: str | None
    """Reason for skipping, or None if following up."""


# ── Follow-up type labels for admin visibility ──────────────────────────────

FU_TYPE_LABELS: dict[str, str] = {
    "price_reminder": "Narx eslatma",
    "catalog_nudge": "Katalog taklif",
    "measurement_push": "O'lchov taklif",
    "soft_reactivation": "Yumshoq qayta aloqa",
    "manager_call_offer": "Menejer qo'ng'iroq",
    "budget_option_offer": "Byudjet variant",
    "none": "\u2014",
}


# ── Follow-up messages (short, natural, Uzbek) ──────────────────────────────

_FU_MESSAGES: dict[str, str] = {
    "price_reminder": (
        "Salom! Narx bo'yicha so'rovingiz qoldi. "
        "Xona maydonini aytsangiz, tez hisoblab beraman \U0001f642"
    ),
    "catalog_nudge": (
        "Katalogimizda yangi dizaynlar bor \u2014 "
        "xonangizga mos variantni ko'rsatib beraymi? \U0001f642"
    ),
    "measurement_push": (
        "Agar xohlasangiz bugun ustamiz bepul o'lchov qilib "
        "aniq narx chiqarib beradi. Majburiyat yo'q \U0001f642"
    ),
    "soft_reactivation": (
        "Salom! Oldingi suhbatimiz qoldi \u2014 "
        "potolok bo'yicha yordam kerakmi? \U0001f642"
    ),
    "manager_call_offer": (
        "Mutaxassisimiz siz bilan bog'lanib, "
        "barcha savollaringizga javob beradi. "
        "Telefon raqamingizni yuboring \U0001f4de"
    ),
    "budget_option_offer": (
        "Byudjet variantimiz ham bor \u2014 "
        "sifatli, 80 000 so'm/m\u00b2 dan. "
        "Xona maydonini aytsangiz hisoblayman \U0001f642"
    ),
}


# ── Safety constants ─────────────────────────────────────────────────────────

MAX_FOLLOWUP_COUNT = 5
_RECENTLY_ACTIVE_MINUTES = 10
_MIN_BETWEEN_SAME_TYPE_HOURS = 12


# ── Main decision function ───────────────────────────────────────────────────


def decide_follow_up(
    *,
    score: int = 0,
    deal_probability_percent: int | None = None,
    buyer_type: str | None = None,
    decision_stage: str | None = None,
    engagement_trend: str | None = None,
    last_objection: str | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    has_district: bool = False,
    has_design: bool = False,
    closing_attempted: bool = False,
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    follow_up_count: int = 0,
    last_activity_ts: int | None = None,
    closing_confidence: float | None = None,
    lead_temperature: str | None = None,
    previous_fu_type: str | None = None,
) -> FollowUpDecision:
    """Decide whether, when, and how to follow up with a lead.

    All parameters are keyword-only with safe defaults.
    Pure function — no I/O, fully deterministic (except time.time()).
    """
    now = int(time.time())
    prob = deal_probability_percent or 0

    # ── Skip checks (safety first) ──────────────────────────────────
    skip = _check_skip(
        follow_up_count=follow_up_count,
        last_activity_ts=last_activity_ts,
        now=now,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        score=score,
    )
    if skip:
        return FollowUpDecision(
            should_follow_up=False,
            follow_up_delay_minutes=None,
            follow_up_type="none",
            follow_up_message="",
            follow_up_reason="",
            skip_reason=skip,
        )

    # ── Select follow-up type ───────────────────────────────────────
    fu_type, reason = _select_type(
        score=score,
        prob=prob,
        buyer_type=buyer_type,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        last_objection=last_objection,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        has_design=has_design,
        closing_attempted=closing_attempted,
        negotiation_tactic=negotiation_tactic,
        negotiation_escalated=negotiation_escalated,
        closing_confidence=closing_confidence,
        previous_fu_type=previous_fu_type,
    )

    # ── Determine delay ─────────────────────────────────────────────
    delay = _compute_delay(
        fu_type=fu_type,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        prob=prob,
        lead_temperature=lead_temperature,
        follow_up_count=follow_up_count,
    )

    message = _FU_MESSAGES.get(fu_type, "")

    return FollowUpDecision(
        should_follow_up=True,
        follow_up_delay_minutes=delay,
        follow_up_type=fu_type,
        follow_up_message=message,
        follow_up_reason=reason,
        skip_reason=None,
    )


# ── Skip logic ───────────────────────────────────────────────────────────────


def _check_skip(
    *,
    follow_up_count: int,
    last_activity_ts: int | None,
    now: int,
    decision_stage: str | None,
    engagement_trend: str | None,
    score: int,
) -> str | None:
    """Return skip reason string, or None if follow-up should proceed."""

    # Cap reached
    if follow_up_count >= MAX_FOLLOWUP_COUNT:
        return f"Follow-up limiti ({MAX_FOLLOWUP_COUNT}) ga yetdi"

    # Recently active — don't disturb
    if last_activity_ts:
        minutes_ago = (now - last_activity_ts) / 60
        if minutes_ago < _RECENTLY_ACTIVE_MINUTES:
            return f"Foydalanuvchi {int(minutes_ago)} daqiqa oldin faol"

    # Cold + cooling + low score — give up
    if (
        decision_stage == "cold"
        and engagement_trend == "cooling_down"
        and score < 15
    ):
        return "Sovuq lid, pasayish trendi, past ball"

    return None


# ── Type selection ───────────────────────────────────────────────────────────


def _select_type(
    *,
    score: int,
    prob: int,
    buyer_type: str | None,
    decision_stage: str | None,
    engagement_trend: str | None,
    last_objection: str | None,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
    has_design: bool,
    closing_attempted: bool,
    negotiation_tactic: str | None,
    negotiation_escalated: bool,
    closing_confidence: float | None,
    previous_fu_type: str | None,
) -> tuple[str, str]:
    """Return (follow_up_type, reason). Avoids repeating previous_fu_type."""

    # ── Rule 1: Escalation flag → manager call ──────────────────────
    if negotiation_escalated:
        return _avoid_repeat(
            "manager_call_offer",
            "Muzokara eskalatsiyasi — menejer kerak",
            previous_fu_type,
        )

    # ── Rule 2: close_ready + warming_up + high prob → measurement ──
    if (
        decision_stage == "close_ready"
        and engagement_trend == "warming_up"
        and prob >= 60
    ):
        return _avoid_repeat(
            "measurement_push",
            "Sotuvga tayyor, isitilmoqda, yuqori ehtimol",
            previous_fu_type,
        )

    # ── Rule 3: close_ready (any trend) + phone → measurement ──────
    if decision_stage == "close_ready" and phone_captured:
        return _avoid_repeat(
            "measurement_push",
            "Sotuvga tayyor, telefon bor",
            previous_fu_type,
        )

    # ── Rule 4: price_sensitive + expensive objection → budget ──────
    if buyer_type == "price_sensitive" and last_objection == "expensive":
        return _avoid_repeat(
            "budget_option_offer",
            "Narxga sezgir xaridor, narx e'tirozi",
            previous_fu_type,
        )

    # ── Rule 5: Repeated objections + no phone → manager ────────────
    if (
        last_objection in ("expensive", "compare")
        and negotiation_tactic
        and negotiation_tactic != "none"
        and not phone_captured
    ):
        return _avoid_repeat(
            "manager_call_offer",
            "Takroriy e'tiroz, muzokara faol, telefon yo'q",
            previous_fu_type,
        )

    # ── Rule 6: quality_buyer + design/catalog → catalog nudge ──────
    if buyer_type == "quality_buyer" and (has_design or decision_stage == "comparing"):
        return _avoid_repeat(
            "catalog_nudge",
            "Sifat xaridori, dizayn/katalog qiziqishi",
            previous_fu_type,
        )

    # ── Rule 7: researching + stable → catalog nudge ────────────────
    if decision_stage == "researching" and engagement_trend == "stable":
        return _avoid_repeat(
            "catalog_nudge",
            "Tadqiq qilmoqda, barqaror trend",
            previous_fu_type,
        )

    # ── Rule 8: delayed + cooling → soft reactivation ───────────────
    if decision_stage in ("delayed", "cold") or engagement_trend == "cooling_down":
        return _avoid_repeat(
            "soft_reactivation",
            "Kechiktirilgan yoki sovumoqda",
            previous_fu_type,
        )

    # ── Rule 9: reactivated → measurement push (strike while hot) ──
    if engagement_trend == "reactivated":
        return _avoid_repeat(
            "measurement_push",
            "Qayta faollashgan — tez harakat",
            previous_fu_type,
        )

    # ── Rule 10: has area + no closing → price reminder ─────────────
    if has_area and not closing_attempted:
        return _avoid_repeat(
            "price_reminder",
            "Maydon ma'lum, closing yo'q",
            previous_fu_type,
        )

    # ── Rule 11: negotiating stage → budget option ──────────────────
    if decision_stage == "negotiating":
        return _avoid_repeat(
            "budget_option_offer",
            "Muzokara bosqichida",
            previous_fu_type,
        )

    # ── Default: price reminder (safest) ────────────────────────────
    return _avoid_repeat(
        "price_reminder",
        "Standart follow-up",
        previous_fu_type,
    )


def _avoid_repeat(
    preferred: str, reason: str, previous: str | None
) -> tuple[str, str]:
    """If preferred type matches previous, rotate to a different type."""
    if previous and preferred == previous:
        # Rotation fallback chain
        _fallback: dict[str, str] = {
            "price_reminder": "catalog_nudge",
            "catalog_nudge": "measurement_push",
            "measurement_push": "price_reminder",
            "soft_reactivation": "catalog_nudge",
            "manager_call_offer": "measurement_push",
            "budget_option_offer": "price_reminder",
        }
        rotated = _fallback.get(preferred, "price_reminder")
        return rotated, f"{reason} (avvalgi: {FU_TYPE_LABELS.get(previous, previous)}, almashtirildi)"
    return preferred, reason


# ── Delay computation ────────────────────────────────────────────────────────


def _compute_delay(
    *,
    fu_type: str,
    decision_stage: str | None,
    engagement_trend: str | None,
    prob: int,
    lead_temperature: str | None,
    follow_up_count: int,
) -> int:
    """Return delay in minutes until the follow-up should fire."""

    # Base delays by type
    _base_delays: dict[str, int] = {
        "measurement_push": 20,
        "price_reminder": 180,       # 3 hours
        "catalog_nudge": 180,        # 3 hours
        "budget_option_offer": 120,  # 2 hours
        "manager_call_offer": 60,    # 1 hour
        "soft_reactivation": 1440,   # 24 hours
    }
    delay = _base_delays.get(fu_type, 360)  # default 6h

    # Stage-based adjustments
    if decision_stage == "close_ready":
        delay = min(delay, 20)  # cap at 20 min for close-ready
    elif decision_stage == "delayed":
        delay = max(delay, 1440)  # minimum 24h for delayed

    # Trend adjustments
    if engagement_trend == "warming_up" and delay > 60:
        delay = max(60, delay // 2)  # halve but floor at 1h
    elif engagement_trend == "cooling_down":
        delay = max(delay, 360)  # minimum 6h for cooling

    # High probability → faster follow-up
    if prob >= 70 and delay > 30:
        delay = max(30, delay // 2)

    # Temperature override for hot leads
    if lead_temperature == "hot" and delay > 60:
        delay = 60

    # Progressive backoff: each subsequent follow-up adds 50%
    if follow_up_count > 0:
        multiplier = 1.0 + (follow_up_count * 0.5)
        delay = round(delay * multiplier)

    # Hard caps
    delay = max(10, min(delay, 2880))  # between 10 min and 48 hours

    return delay
