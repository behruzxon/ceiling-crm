"""
apps.bot.handlers.private.ai_openai
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
OpenAI integration: client, context builder, conversation DB helpers,
and the main ``_call_ai`` function.

No dependencies on other ``ai_*`` sibling modules.
"""
from __future__ import annotations

import json
import time
from typing import Any

import sqlalchemy as sa
import httpx
from openai import AsyncOpenAI
from sqlalchemy.dialects.postgresql import insert as pg_insert

from apps.bot.ai.system_prompt import _SUMMARY_SYSTEM, _SYSTEM_PROMPT
from infrastructure.database.models.ai_conversation import AiConversationModel
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from infrastructure.monitoring.prometheus import (
    openai_tokens_prompt_total,
    openai_tokens_completion_total,
    openai_requests_total,
    openai_request_duration,
)
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)


def _record_usage(resp: Any, model: str, duration: float) -> None:
    """Record OpenAI response usage in Prometheus counters. Never raises."""
    try:
        openai_requests_total.labels(model=model, status="ok").inc()
        openai_request_duration.labels(model=model).observe(duration)
        usage = getattr(resp, "usage", None)
        if usage:
            openai_tokens_prompt_total.labels(model=model).inc(usage.prompt_tokens or 0)
            openai_tokens_completion_total.labels(model=model).inc(usage.completion_tokens or 0)
    except Exception:
        pass

# ── Tuneable constants ───────────────────────────────────────────────────────

_MAX_MESSAGES = 12           # rolling window size stored in ai_conversations
_HISTORY_TO_SEND = 8         # how many messages to pass to OpenAI per call
_SUMMARY_EVERY_N_TURNS = 10  # regenerate summary every N user turns


# ── OpenAI client (lazy singleton) ──────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        api_key = (
            settings.ai.api_key.get_secret_value()
            if settings.ai.api_key
            else settings.openai.api_key.get_secret_value()
        )
        _openai_client = AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
    return _openai_client


# ── Context builder ─────────────────────────────────────────────────────────

def _build_context_block(
    profile: dict[str, Any],
    summary: str | None,
) -> str | None:
    """Build the per-request dynamic context injected as a second system message."""
    parts: list[str] = []

    profile_parts: list[str] = []
    if design := profile.get("interested_design"):
        profile_parts.append(f"qiziqayotgan dizayn: {design}")
    if dims := profile.get("last_dimensions"):
        profile_parts.append(f"so'nggi o'lcham: {dims}")
    if location := profile.get("location"):
        profile_parts.append(f"joylashuv: {location}")
    if profile_parts:
        parts.append("Profil: " + "; ".join(profile_parts))

    if summary:
        parts.append(f"Suhbat qisqartmasi: {summary}")

    if last_intent := profile.get("last_intent"):
        parts.append(f"Oxirgi CTA turi: {last_intent}")

    if not parts:
        return None

    return "--- FOYDALANUVCHI KONTEKSTI ---\n" + "\n".join(parts)


# ── DB helpers (all non-fatal) ──────────────────────────────────────────────

async def _load_context(
    user_id: int,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Load profile + conversation from DB.
    Returns (profile, messages, summary) — empty defaults on any error.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            mem = await session.get(AiMemoryModel, user_id)
            profile: dict[str, Any] = mem.profile if mem else {}

            conv = await session.get(AiConversationModel, user_id)
            messages: list[dict[str, str]] = conv.last_messages if conv else []
            summary: str | None = conv.summary if conv else None

        return profile, messages, summary
    except Exception:
        log.warning("ai_context_load_failed", user_id=user_id)
        return {}, [], None


async def _regenerate_summary(messages: list[dict[str, str]]) -> str:
    """Summarise the conversation in 2-4 lines. Raises on failure."""
    client = _get_client()
    settings = get_settings()
    model = settings.ai.model
    history_text = "\n".join(
        f"{'Foydalanuvchi' if m['role'] == 'user' else 'Madina'}: {m['text']}"
        for m in messages
    )
    from openai import APIConnectionError, APITimeoutError, RateLimitError
    from shared.utils.retry import with_retry

    t0 = time.monotonic()
    resp = await with_retry(
        client.chat.completions.create,
        model=model,
        temperature=0.1,
        max_tokens=150,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user",   "content": history_text},
        ],
        max_retries=2,
        base_delay=1.0,
        retryable=(APIConnectionError, APITimeoutError, RateLimitError),
        operation="openai_summary",
    )
    _record_usage(resp, model, time.monotonic() - t0)
    return (resp.choices[0].message.content or "").strip()


async def _persist_exchange(
    *,
    user_id: int,
    user_text: str,
    assistant_text: str,
    intent: str,
    extracted: dict[str, Any],
    current_profile: dict[str, Any],
    current_messages: list[dict[str, str]],
    current_summary: str | None,
    lead_temperature: str | None = None,
    closing_confidence: float | None = None,
) -> None:
    """Upsert ai_user_memory + ai_conversations after a successful AI exchange."""
    try:
        new_messages = (
            current_messages
            + [
                {"role": "user",      "text": user_text},
                {"role": "assistant", "text": assistant_text},
            ]
        )[-_MAX_MESSAGES:]

        turn_count = int(current_profile.get("turn_count", 0)) + 1

        new_summary = current_summary
        if turn_count % _SUMMARY_EVERY_N_TURNS == 0:
            try:
                new_summary = await _regenerate_summary(new_messages)
                log.info("ai_summary_regenerated", user_id=user_id, turn=turn_count)
            except Exception:
                log.warning("ai_summary_regen_failed", user_id=user_id)

        new_profile: dict[str, Any] = {**current_profile}
        for field in ("interested_design", "last_dimensions", "location"):
            value = extracted.get(field)
            if value:
                new_profile[field] = value
        new_profile["last_intent"] = intent
        new_profile["turn_count"] = turn_count

        factory = get_session_factory()
        async with factory() as session:
            conv_values: dict[str, Any] = {
                "user_id": user_id,
                "last_messages": new_messages,
            }
            conv_set: dict[str, Any] = {
                "last_messages": new_messages,
                "updated_at": sa.func.now(),
            }
            if new_summary:
                conv_values["summary"] = new_summary
                if new_summary != current_summary:
                    conv_set["summary"] = new_summary
            if lead_temperature is not None:
                conv_values["lead_temperature"] = lead_temperature
                conv_set["lead_temperature"] = lead_temperature
            if closing_confidence is not None:
                conv_values["closing_confidence"] = closing_confidence
                conv_set["closing_confidence"] = closing_confidence

            await session.execute(
                pg_insert(AiConversationModel)
                .values(**conv_values)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_=conv_set,
                )
            )

            await session.execute(
                pg_insert(AiMemoryModel)
                .values(user_id=user_id, profile=new_profile)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "profile": new_profile,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()

    except Exception:
        log.warning("ai_persist_exchange_failed", user_id=user_id)


async def clear_ai_conversation(user_id: int) -> None:
    """Reset the active conversation thread for a user (called on /start).

    Clears last_messages and summary.  Does NOT touch ai_user_memory.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                pg_insert(AiConversationModel)
                .values(user_id=user_id, last_messages=[], summary=None)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "last_messages": [],
                        "summary": None,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()
        log.info("ai_conversation_cleared", user_id=user_id)
    except Exception:
        log.warning("ai_conversation_clear_failed", user_id=user_id)


async def _store_user_message_only(
    *,
    user_id: int,
    user_text: str,
    current_messages: list[dict[str, str]],
) -> None:
    """Persist the user's message even when the AI call fails."""
    try:
        new_messages = (
            current_messages + [{"role": "user", "text": user_text}]
        )[-_MAX_MESSAGES:]

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                pg_insert(AiConversationModel)
                .values(user_id=user_id, last_messages=new_messages)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "last_messages": new_messages,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()
    except Exception:
        log.warning("ai_user_msg_store_failed", user_id=user_id)


# ── OpenAI call ─────────────────────────────────────────────────────────────

async def _call_ai(
    user_text: str,
    history: list[dict[str, str]],
    context_block: str | None,
) -> dict[str, Any]:
    """Build messages, call OpenAI, return parsed JSON dict."""
    settings = get_settings()
    client = _get_client()
    model = settings.ai.model

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
    ]
    if context_block:
        messages.append({"role": "system", "content": context_block})

    for msg in history[-_HISTORY_TO_SEND:]:
        messages.append({"role": msg["role"], "content": msg["text"]})

    messages.append({"role": "user", "content": user_text})

    from openai import APIConnectionError, APITimeoutError, RateLimitError
    from shared.utils.retry import with_retry

    t0 = time.monotonic()
    try:
        resp = await with_retry(
            client.chat.completions.create,
            model=model,
            temperature=0.3,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=messages,
            max_retries=3,
            base_delay=1.0,
            retryable=(APIConnectionError, APITimeoutError, RateLimitError),
            operation="openai_chat",
        )
    except Exception:
        openai_requests_total.labels(model=model, status="error").inc()
        raise
    _record_usage(resp, model, time.monotonic() - t0)
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)
