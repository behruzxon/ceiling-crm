"""Admin chat history viewer routes.

GET /admin/api/chats            — list all AI conversation summaries for tenant
GET /admin/api/chats/{user_id}  — full conversation history for one user
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import get_current_admin
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.ai_conversation import AiConversationModel
from infrastructure.database.session import get_db

router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────

class ChatSummary(BaseModel):
    user_id: int
    message_count: int
    last_message: str | None
    lead_temperature: str | None
    updated_at: datetime


class ChatMessage(BaseModel):
    role: str
    text: str


class ChatDetail(BaseModel):
    user_id: int
    messages: list[ChatMessage]
    summary: str | None
    lead_temperature: str | None
    closing_confidence: float | None
    updated_at: datetime


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ChatSummary])
async def list_chats(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSummary]:
    """Return paginated AI conversation summaries for the current tenant."""
    result = await db.execute(
        select(AiConversationModel)
        .where(AiConversationModel.tenant_id == admin.tenant_id)
        .order_by(AiConversationModel.updated_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.scalars().all()

    summaries: list[ChatSummary] = []
    for row in rows:
        msgs: list[dict] = row.last_messages or []
        last_text: str | None = None
        if msgs:
            last_text = (msgs[-1].get("text") or "")[:120]
        summaries.append(
            ChatSummary(
                user_id=row.user_id,
                message_count=len(msgs),
                last_message=last_text,
                lead_temperature=row.lead_temperature,
                updated_at=row.updated_at,
            )
        )
    return summaries


@router.get("/{user_id}", response_model=ChatDetail)
async def get_chat(
    user_id: int,
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ChatDetail:
    """Return the full conversation history for a specific user (tenant-scoped).

    Uses the composite PK (tenant_id, user_id) for lookup.
    """
    conv = await db.get(AiConversationModel, (admin.tenant_id, user_id))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    messages = [
        ChatMessage(role=m.get("role", "user"), text=m.get("text", ""))
        for m in (conv.last_messages or [])
    ]
    return ChatDetail(
        user_id=conv.user_id,
        messages=messages,
        summary=conv.summary,
        lead_temperature=conv.lead_temperature,
        closing_confidence=conv.closing_confidence,
        updated_at=conv.updated_at,
    )
