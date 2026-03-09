"""POST /api/chat/stream — Server-Sent Events AI streaming endpoint.

Streams AI reply tokens as they are generated.  Uses the same rate limiting,
prompt safety, and conversation persistence as the non-streaming endpoint
(``/api/chat/message``), but yields SSE events instead of a single JSON body.

SSE event format::

    data: {"type":"token","data":"Salom"}\n\n
    data: {"type":"token","data":"!"}\n\n
    ...
    data: {"type":"done","session_id":"...","intent":"measurement","is_ai":true}\n\n

On error::

    data: {"type":"error","message":"..."}\n\n

The ``intent`` field in the ``done`` event is detected via keyword heuristics
(see ``core.services.ai_engine._detect_intent``) since OpenAI JSON mode is
incompatible with streaming.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import chat_user_id as _chat_user_id, get_tenant_id
from core.schemas.chat_schemas import ChatMessageRequest
from core.security.prompt_sanitizer import scan_prompt
from core.services.ai_engine import (
    _build_context_block,
    _detect_intent,
    _load_context,
    _persist_exchange,
    check_ai_rate_limit,
    generate_stream,
)
from infrastructure.database.session import get_db
from infrastructure.di import get_tenant_ai_config

router = APIRouter()


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(
    payload: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> StreamingResponse:
    """Stream AI reply tokens via Server-Sent Events.

    The response body is a sequence of SSE events; callers should read it with
    ``fetch()`` + ``ReadableStream`` (not ``EventSource``, which is GET-only).
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        user_id = _chat_user_id(payload.session_id)

        # ── Prompt safety ─────────────────────────────────────────────────────
        scan = scan_prompt(payload.message)
        if scan.blocked:
            yield _sse({
                "type": "error",
                "message": "Kechirasiz, bu so\u02bcrovni qayta ishlashim mumkin emas.",
            })
            return

        # ── Rate limiting ─────────────────────────────────────────────────────
        allowed, reason = await check_ai_rate_limit(user_id, tenant_id)
        if not allowed:
            yield _sse({
                "type": "error",
                "message": (
                    "So\u02bcrovlar limiti oshib ketdi. Keyinroq qayta urinib ko\u02bcring."
                    if reason == "user"
                    else "Kunlik AI limiti tugadi."
                ),
            })
            return

        # ── Load context ──────────────────────────────────────────────────────
        profile, history, summary = await _load_context(user_id, tenant_id=tenant_id)

        # ── Build system prompt + context block ───────────────────────────────
        tenant_prompt, _kb = await get_tenant_ai_config(db, tenant_id)
        context_block = _build_context_block(profile, summary)

        # ── Stream tokens ─────────────────────────────────────────────────────
        buf: list[str] = []
        try:
            async with asyncio.timeout(28):
                async for token in generate_stream(
                    scan.sanitized_text,
                    history,
                    context_block,
                    tenant_prompt,
                ):
                    buf.append(token)
                    yield _sse({"type": "token", "data": token})

        except TimeoutError:
            yield _sse({
                "type": "error",
                "message": "AI javobi vaqt chegarasidan oshdi. Qayta urinib ko\u02bcring.",
            })
            return
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("stream_ai_error: %s", exc)
            yield _sse({
                "type": "error",
                "message": "AI xizmati vaqtincha mavjud emas.",
            })
            return

        # ── Detect intent + persist (non-fatal) ───────────────────────────────
        full_reply = "".join(buf)
        intent = _detect_intent(full_reply)

        try:
            await _persist_exchange(
                user_id=user_id,
                tenant_id=tenant_id,
                user_text=scan.sanitized_text,
                assistant_text=full_reply,
                intent=intent,
                extracted={},
                current_profile=profile,
                current_messages=history,
                current_summary=summary,
            )
        except Exception:
            pass  # persistence is non-fatal

        # ── Done event ────────────────────────────────────────────────────────
        yield _sse({
            "type": "done",
            "session_id": payload.session_id,
            "intent": intent,
            "is_ai": True,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
