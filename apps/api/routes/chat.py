"""POST /api/chat/message — AI-powered chat endpoint.

Reuses channel-agnostic AI functions from apps/bot/handlers/private/ai_openai.py.
Phase 3 will move these to core/services/ai_engine.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import chat_user_id as _chat_user_id, get_tenant_id
from core.services.ai_engine import (
    _build_context_block,
    _call_ai,
    _load_context,
    _persist_exchange,
    check_ai_rate_limit,
)
from core.domain.ai_response import parse_ai_response
from core.schemas.chat_schemas import ChatMessageRequest, ChatMessageResponse
from core.security.prompt_sanitizer import scan_prompt
from core.services.ai_cache_service import get_cached_response, store_response
from infrastructure.database.session import get_db
from infrastructure.di import get_tenant_ai_config

router = APIRouter()


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    payload: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> ChatMessageResponse:
    user_id = _chat_user_id(payload.session_id)

    # ── Prompt safety ──────────────────────────────────────────────────────────
    scan = scan_prompt(payload.message)
    if scan.blocked:
        return ChatMessageResponse(
            session_id=payload.session_id,
            reply="Kechirasiz, bu so'rovni qayta ishlashim mumkin emas.",
            intent="blocked",
        )

    # ── Rate limiting (per-user sliding window + per-tenant daily quota) ───────
    allowed, reason = await check_ai_rate_limit(user_id, tenant_id)
    if not allowed:
        detail = (
            "So'rovlar limiti oshib ketdi. Keyinroq qayta urinib ko'ring."
            if reason == "user"
            else "Kunlik AI limiti tugadi."
        )
        raise HTTPException(status_code=429, detail=detail)

    # ── Load conversation context ───────────────────────────────────────────────
    profile, history, summary = await _load_context(user_id, tenant_id=tenant_id)

    # ── Cache lookup (skipped when conversation history exists) ────────────────
    cached = await get_cached_response(tenant_id, payload.message, has_history=bool(history))
    if cached:
        ai_result = cached
    else:
        tenant_prompt, _kb = await get_tenant_ai_config(db, tenant_id)
        context_block = _build_context_block(profile, summary)
        ai_result = await _call_ai(
            scan.sanitized_text,
            history,
            context_block,
            system_prompt=tenant_prompt,
        )
        await store_response(
            tenant_id, payload.message, ai_result, has_history=bool(history)
        )

    reply_payload = parse_ai_response(ai_result)

    # ── Persist exchange (non-fatal) ────────────────────────────────────────────
    await _persist_exchange(
        user_id=user_id,
        tenant_id=tenant_id,
        user_text=scan.sanitized_text,
        assistant_text=reply_payload.reply,
        intent=reply_payload.intent,
        extracted=reply_payload.extracted.model_dump(),
        current_profile=profile,
        current_messages=history,
        current_summary=summary,
        lead_temperature=reply_payload.lead_temperature,
        closing_confidence=reply_payload.closing_confidence,
    )

    return ChatMessageResponse(
        session_id=payload.session_id,
        reply=reply_payload.reply,
        intent=reply_payload.intent,
    )
