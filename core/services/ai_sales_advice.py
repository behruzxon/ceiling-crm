"""
core.services.ai_sales_advice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI-powered sales advice for individual leads.

Uses OpenAI to analyze a lead's profile, score, pipeline stage, and
inactivity time, then generates a recommended next action with a
suggested message in Uzbek.

Results are cached in Redis for 30 minutes to control API costs.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

# ── Safety-aware system prompt ────────────────────────────────────────────────

_SALES_ADVICE_SYSTEM = """Sen professional sotuv maslahatchisisan. Stretch ceiling kompaniyasi uchun ishlaysan (O'zbekiston bozori).

VAZIFA: Berilgan lid ma'lumotlari asosida sotuvchi uchun keyingi eng yaxshi qadamni tavsiya qil.

QOIDALAR (MAJBURIY):
- Hech qachon amalga oshirib bo'lmaydigan narsalarni va'da qilma
- Agressiv sotuv tilidan foydalanma
- Har doim xushmuomala va professional bo'l
- O'zbek tiliga mos ohangda yoz
- Faqat real va foydali maslahat ber
- Narxlarni to'g'ridan-to'g'ri aytma — faqat "bepul o'lchov", "maxsus chegirma" kabi umumiy taklif ber
- Mijozning shaxsiy hayotiga aralashma

JAVOB FORMATI (JSON):
{
  "lead_status": "HOT / WARM / COLD",
  "recommended_actions": ["harakat 1", "harakat 2", "harakat 3"],
  "suggested_message": "Mijozga yuboriladigan xabar matni",
  "reasoning": "Nima uchun bu tavsiya berildi"
}"""


@dataclass(frozen=True)
class SalesAdvice:
    """Result of AI sales advice generation."""
    lead_status: str              # HOT / WARM / COLD
    recommended_actions: list[str]
    suggested_message: str
    reasoning: str
    cached: bool = False


# ── Core function ─────────────────────────────────────────────────────────────


async def generate_sales_advice(
    *,
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    lead_district: str,
    lead_score: int,
    lead_classification: str,
    pipeline_stage: str,
    room_area: float | None = None,
    package_type: str | None = None,
    closing_confidence: float | None = None,
    hours_inactive: float | None = None,
    last_messages: list[str] | None = None,
    use_cache: bool = True,
) -> SalesAdvice:
    """Generate AI sales advice for a lead.

    Checks Redis cache first (30-min TTL). On cache miss, calls OpenAI
    and stores the result.

    Args:
        lead_id: Lead database ID (used as cache key).
        lead_name: Customer name.
        lead_phone: Customer phone (may be "—" if unknown).
        lead_district: Customer district.
        lead_score: Numeric score 0-100.
        lead_classification: "hot" / "warm" / "cold".
        pipeline_stage: Current pipeline stage value.
        room_area: Room area in m² (if known).
        package_type: Selected package (standard/premium/vip).
        closing_confidence: AI closing confidence 0-1.
        hours_inactive: Hours since last activity.
        last_messages: Recent user messages (up to 5).
        use_cache: Whether to check/store Redis cache.

    Returns:
        SalesAdvice dataclass with recommended actions and message.
    """
    # ── Check cache ──────────────────────────────────────────────────────
    if use_cache:
        cached = await _get_cached_advice(lead_id)
        if cached is not None:
            return cached

    # ── Build context prompt ─────────────────────────────────────────────
    context = _build_context(
        lead_name=lead_name,
        lead_phone=lead_phone,
        lead_district=lead_district,
        lead_score=lead_score,
        lead_classification=lead_classification,
        pipeline_stage=pipeline_stage,
        room_area=room_area,
        package_type=package_type,
        closing_confidence=closing_confidence,
        hours_inactive=hours_inactive,
        last_messages=last_messages,
    )

    # ── Call OpenAI ──────────────────────────────────────────────────────
    try:
        result = await _call_openai(context)
    except Exception:
        log.exception("ai_sales_advice_openai_failed", lead_id=lead_id)
        return _fallback_advice(lead_classification, hours_inactive)

    advice = SalesAdvice(
        lead_status=result.get("lead_status", lead_classification.upper()),
        recommended_actions=result.get("recommended_actions", []),
        suggested_message=result.get("suggested_message", ""),
        reasoning=result.get("reasoning", ""),
    )

    # ── Store in cache ───────────────────────────────────────────────────
    if use_cache:
        await _set_cached_advice(lead_id, advice)

    return advice


# ── OpenAI call ───────────────────────────────────────────────────────────────


def _build_context(
    *,
    lead_name: str,
    lead_phone: str,
    lead_district: str,
    lead_score: int,
    lead_classification: str,
    pipeline_stage: str,
    room_area: float | None,
    package_type: str | None,
    closing_confidence: float | None,
    hours_inactive: float | None,
    last_messages: list[str] | None,
) -> str:
    """Build the user prompt with lead context."""
    lines = [
        f"LID MA'LUMOTLARI:",
        f"- Ism: {lead_name}",
        f"- Telefon: {lead_phone}",
        f"- Tuman: {lead_district}",
        f"- Ball: {lead_score}/100 ({lead_classification.upper()})",
        f"- Bosqich: {pipeline_stage}",
    ]
    if room_area:
        lines.append(f"- Xona maydoni: {room_area} m²")
    if package_type:
        lines.append(f"- Tanlangan paket: {package_type}")
    if closing_confidence is not None:
        lines.append(f"- Yopish ehtimoli: {closing_confidence:.0%}")
    if hours_inactive is not None:
        lines.append(f"- Oxirgi faollik: {hours_inactive:.0f} soat oldin")
    else:
        lines.append("- Oxirgi faollik: noma'lum")

    if last_messages:
        lines.append("\nOXIRGI XABARLAR:")
        for msg in last_messages[:5]:
            lines.append(f'  - "{msg[:200]}"')

    lines.append("\nShu lid uchun eng yaxshi keyingi qadamni tavsiya qil.")
    return "\n".join(lines)


async def _call_openai(context: str) -> dict[str, Any]:
    """Call OpenAI with sales advice system prompt + lead context."""
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    from apps.bot.handlers.private.ai_openai import _get_client, _record_usage
    from infrastructure.monitoring.prometheus import openai_requests_total
    from shared.config import get_settings
    from shared.utils.retry import with_retry

    settings = get_settings()
    client = _get_client()
    model = settings.ai.model

    messages = [
        {"role": "system", "content": _SALES_ADVICE_SYSTEM},
        {"role": "user", "content": context},
    ]

    t0 = time.monotonic()
    try:
        resp = await with_retry(
            client.chat.completions.create,
            model=model,
            temperature=0.4,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=messages,
            max_retries=2,
            base_delay=1.0,
            retryable=(APIConnectionError, APITimeoutError, RateLimitError),
            operation="ai_sales_advice",
        )
    except Exception:
        openai_requests_total.labels(model=model, status="error").inc()
        raise

    _record_usage(resp, model, time.monotonic() - t0)
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


# ── Redis caching ─────────────────────────────────────────────────────────────


async def _get_cached_advice(lead_id: int) -> SalesAdvice | None:
    """Return cached advice or None."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        redis = get_redis()
        data = await redis.get_json(CacheKeys.ai_lead_advice(lead_id))
        if data is None:
            return None
        return SalesAdvice(
            lead_status=data["lead_status"],
            recommended_actions=data["recommended_actions"],
            suggested_message=data["suggested_message"],
            reasoning=data["reasoning"],
            cached=True,
        )
    except Exception:
        log.warning("ai_advice_cache_read_failed", lead_id=lead_id)
        return None


async def _set_cached_advice(lead_id: int, advice: SalesAdvice) -> None:
    """Store advice in Redis with 30-min TTL."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()
        data = {
            "lead_status": advice.lead_status,
            "recommended_actions": advice.recommended_actions,
            "suggested_message": advice.suggested_message,
            "reasoning": advice.reasoning,
        }
        await redis.set_json(
            CacheKeys.ai_lead_advice(lead_id),
            data,
            ttl=CacheTTL.AI_LEAD_ADVICE,
        )
    except Exception:
        log.warning("ai_advice_cache_write_failed", lead_id=lead_id)


# ── Deterministic fallback (no OpenAI needed) ────────────────────────────────


def _fallback_advice(
    classification: str,
    hours_inactive: float | None,
) -> SalesAdvice:
    """Return deterministic advice when OpenAI is unavailable."""
    cl = classification.lower()

    if cl == "hot":
        return SalesAdvice(
            lead_status="HOT",
            recommended_actions=[
                "Darhol bog'laning",
                "Bepul o'lchov taklif qiling",
                "Joriy chegirma haqida xabar bering",
            ],
            suggested_message=(
                "Assalomu alaykum! Agar xohlasangiz, ustamiz bepul o'lchov "
                "qilib berishi mumkin. Qaysi vaqt sizga qulay?"
            ),
            reasoning="HOT lid — tezda harakat qilish kerak",
        )
    elif cl == "warm":
        actions = ["Xona o'lchami haqida so'rang", "Katalog yuboring"]
        if hours_inactive and hours_inactive > 24:
            actions.append("Maxsus taklif bilan qayta aloqa qiling")
        return SalesAdvice(
            lead_status="WARM",
            recommended_actions=actions,
            suggested_message=(
                "Assalomu alaykum! Potalok dizaynlarimiz katalogini "
                "ko'rib chiqmoqchimisiz? 😊"
            ),
            reasoning="WARM lid — qiziqishni kuchaytirish kerak",
        )
    else:
        return SalesAdvice(
            lead_status="COLD",
            recommended_actions=[
                "Aktsiya haqida xabar yuboring",
                "2-3 kun keyin qayta aloqa qiling",
            ],
            suggested_message=(
                "Assalomu alaykum! Hozirda maxsus narxlar mavjud. "
                "Qiziqsangiz yozing 😊"
            ),
            reasoning="COLD lid — yumshoq eslatma bilan qayta faollashtirish",
        )
