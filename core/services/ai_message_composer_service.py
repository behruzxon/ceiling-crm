"""
core.services.ai_message_composer_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generates personalized follow-up messages via OpenAI.

Falls back to deterministic templates on any failure (timeout, invalid
output, API error). Never raises — always returns usable text.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

_UNSAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b100\s*%\b", re.IGNORECASE),
    re.compile(r"\beng arzon\b", re.IGNORECASE),
    re.compile(r"\baniq narx\b", re.IGNORECASE),
    re.compile(r"\bkafolat beramiz\b", re.IGNORECASE),
    re.compile(r"\+998\d{9}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]", re.IGNORECASE),
    re.compile(r"token[=:]", re.IGNORECASE),
]

_SYSTEM_PROMPT = (
    "Sen VASHPOTOLOK kompaniyasining do'stona yordamchisissan.\n"
    "Vazifang: mijozga qisqa, tabiiy follow-up xabar yozish.\n\n"
    "QOIDALAR:\n"
    "- Faqat o'zbek tilida yoz.\n"
    "- 1-3 gap, 150 belgidan oshma.\n"
    "- 0-1 ta emoji ishlat.\n"
    "- Narx faqat berilgan ma'lumotda bo'lsa ayt, o'ylab topma.\n"
    "- '100% kafolat', 'eng arzon', 'aniq narx' kabi absolut claimlar qilma.\n"
    "- Xabar oxirida CTA (chaqiruv) bo'lsin.\n"
    "- HTML/markdown ishlatma, oddiy text yoz.\n"
    "- Telefon raqam, parol, token yozma.\n"
)

_TYPE_PROMPTS: dict[str, str] = {
    "catalog": (
        "Mijoz katalogni ko'rdi. {designs_ctx}"
        "Maqsad: kvadrat metrini so'rab narx hisoblashga undash."
    ),
    "price": (
        "Mijoz narx hisobladi. {price_ctx}"
        "Maqsad: buyurtma berishga yoki operator bilan bog'lanishga undash. "
        "Narxni faqat 'taxminiy' deb ayt."
    ),
    "abandoned_order": (
        "Mijoz buyurtma formasini boshladi lekin tugallamadi. {order_ctx}"
        "Maqsad: davom ettirishga yoki telefon yuborishga undash."
    ),
}


def _build_user_prompt(
    followup_type: str,
    memory_data: dict[str, Any],
) -> str:
    name = memory_data.get("full_name") or ""
    offer_hint = ""
    last_offer = memory_data.get("last_dynamic_offer")
    if isinstance(last_offer, dict) and last_offer.get("message_hint"):
        offer_hint = (
            f"\nTaklif yo'nalishi: {last_offer['message_hint']}. "
            "Bu faqat maslahat — narx yoki chegirma o'ylab topma."
        )

    if followup_type == "catalog":
        designs = memory_data.get("interested_designs") or []
        designs_ctx = (
            f"Ko'rgan dizaynlar: {', '.join(designs[:3])}. "
            if designs else ""
        )
        ctx = {"designs_ctx": designs_ctx}
    elif followup_type == "price":
        area = memory_data.get("area_m2")
        price = memory_data.get("estimated_price")
        ceiling = memory_data.get("ceiling_type") or ""
        parts = []
        if area:
            parts.append(f"Maydon: {area}m²")
        if ceiling:
            parts.append(f"Dizayn: {ceiling}")
        if price:
            parts.append(f"Taxminiy narx: {price:,} UZS")
        price_ctx = (". ".join(parts) + ". ") if parts else ""
        ctx = {"price_ctx": price_ctx}
    elif followup_type == "abandoned_order":
        order_parts = []
        if name:
            order_parts.append(f"Ism: {name}")
        if memory_data.get("phone_masked"):
            order_parts.append("Telefon: bor")
        else:
            order_parts.append("Telefon: hali yo'q")
        order_ctx = (". ".join(order_parts) + ". ") if order_parts else ""
        ctx = {"order_ctx": order_ctx}
    else:
        ctx = {}

    template = _TYPE_PROMPTS.get(followup_type, "Mijozga qisqa follow-up yoz.")
    prompt = template.format_map({**{"designs_ctx": "", "price_ctx": "", "order_ctx": ""}, **ctx})

    if name:
        prompt = f"Mijoz ismi: {name}. " + prompt

    if offer_hint:
        prompt += offer_hint

    return prompt


def validate_ai_output(
    text: str,
    followup_type: str,
    memory_data: dict[str, Any],
) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "empty"
    if len(text) > 500:
        return False, "too_long"

    for pat in _UNSAFE_PATTERNS:
        if pat.search(text):
            return False, "unsafe_pattern"

    price_mentioned = bool(re.search(r"\d{3,}", text))
    has_price_in_memory = bool(memory_data.get("estimated_price"))
    if price_mentioned and not has_price_in_memory:
        return False, "invented_price"

    return True, "ok"


async def compose_followup(
    followup_type: str,
    memory_data: dict[str, Any],
    fallback_text: str,
) -> str:
    try:
        from shared.config import get_settings
        biz = get_settings().business
        if not biz.agent_ai_composer_enabled:
            return fallback_text

        from infrastructure.ai.openai_client import get_openai_client
        client = get_openai_client()
        user_prompt = _build_user_prompt(followup_type, memory_data)

        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=biz.agent_ai_composer_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=biz.agent_ai_composer_max_tokens,
                temperature=0.6,
            ),
            timeout=biz.agent_ai_composer_timeout_seconds,
        )

        ai_text = (resp.choices[0].message.content or "").strip()
        ok, reason = validate_ai_output(ai_text, followup_type, memory_data)
        if not ok:
            log.warning("ai_composer_invalid", reason=reason, followup_type=followup_type)
            return fallback_text

        return ai_text

    except asyncio.TimeoutError:
        log.warning("ai_composer_timeout", followup_type=followup_type)
        return fallback_text
    except Exception:
        log.warning("ai_composer_error", followup_type=followup_type)
        return fallback_text
