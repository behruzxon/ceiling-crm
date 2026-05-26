"""
apps.api.routes.admin_crm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRM contacts, messages, notes, tags endpoints. Read + basic write for admin.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies.auth import require_api_token
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm",
    tags=["crm"],
    dependencies=[Depends(require_api_token)],
)


class NoteRequest(BaseModel):
    text: str = Field(..., max_length=2000)

class TagRequest(BaseModel):
    tag: str = Field(..., max_length=30)

class ContactUpdateRequest(BaseModel):
    lead_status: str | None = None
    temperature: str | None = None


@router.get("/contacts")
async def list_contacts(
    q: str = Query(default="", max_length=100),
    status: str = Query(default=""),
    temperature: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    import sqlalchemy as sa
    from infrastructure.database.models.crm_contact import CRMContactModel as C
    stmt = sa.select(C).order_by(C.last_seen_at.desc().nullslast())
    if status:
        stmt = stmt.where(C.lead_status == status)
    if temperature:
        stmt = stmt.where(C.temperature == temperature)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(sa.or_(
            C.username.ilike(like), C.first_name.ilike(like),
            C.last_name.ilike(like),
        ))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [{
        "id": r.id, "telegram_user_id": r.telegram_user_id,
        "username": r.username, "first_name": r.first_name,
        "lead_status": r.lead_status, "lead_score": r.lead_score,
        "temperature": r.temperature,
        "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
    } for r in rows]
    return {"items": items, "count": len(items)}


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    from core.services.crm_contact_service import CRMContactService
    svc = CRMContactService(db)
    c = await svc.get_contact(contact_id)
    if not c:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": c.id, "telegram_user_id": c.telegram_user_id,
        "username": c.username, "first_name": c.first_name,
        "last_name": c.last_name, "phone": c.phone,
        "language_code": c.language_code, "source": c.source,
        "lead_status": c.lead_status, "lead_score": c.lead_score,
        "temperature": c.temperature,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "metadata": c.metadata_json,
    }


@router.get("/contacts/{contact_id}/messages")
async def get_messages(
    contact_id: int, limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.crm_message_service import CRMMessageService
    msgs = await CRMMessageService(db).list_messages(contact_id, limit)
    items = [{
        "id": m.id, "direction": m.direction, "sender_type": m.sender_type,
        "text": m.redacted_text or m.text, "message_type": m.message_type,
        "is_sensitive": m.is_sensitive,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in msgs]
    return {"items": items, "count": len(items)}


@router.post("/contacts/{contact_id}/notes")
async def create_note(
    contact_id: int, body: NoteRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.crm_contact_service import CRMContactService
    note = await CRMContactService(db).add_note(contact_id, body.text, "admin")
    await db.commit()
    return {"status": "created", "note_id": note.id}


@router.post("/contacts/{contact_id}/tags")
async def create_tag(
    contact_id: int, body: TagRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.crm_contact_service import CRMContactService
    ok = await CRMContactService(db).add_tag(contact_id, body.tag)
    await db.commit()
    return {"status": "created" if ok else "duplicate"}


@router.delete("/contacts/{contact_id}/tags/{tag}")
async def delete_tag(
    contact_id: int, tag: str, db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.crm_contact_service import CRMContactService
    ok = await CRMContactService(db).remove_tag(contact_id, tag)
    await db.commit()
    return {"status": "deleted" if ok else "not_found"}


@router.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: int, body: ContactUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.crm_contact_service import CRMContactService
    svc = CRMContactService(db)
    if body.lead_status:
        if not svc.is_valid_status(body.lead_status):
            raise HTTPException(status_code=400, detail="invalid_status")
        await svc.update_lead_status(contact_id, body.lead_status)
    await db.commit()
    return {"status": "updated"}


# ── Operator Reply ───────────────────────────────────────────────────────────


class ReplyRequest(BaseModel):
    text: str = Field(..., max_length=1000)
    confirm: bool = Field(default=False)


@router.post("/contacts/{contact_id}/reply/preview")
async def preview_reply(
    contact_id: int, body: ReplyRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    from dataclasses import asdict
    from core.services.crm_contact_service import CRMContactService
    from core.services.crm_operator_reply_service import CRMOperatorReplyService
    from shared.config import get_settings
    biz = get_settings().business
    c = await CRMContactService(db).get_contact(contact_id)
    contact_dict = {
        "telegram_user_id": c.telegram_user_id if c else None,
        "telegram_chat_id": c.telegram_chat_id if c else None,
        "lead_status": c.lead_status if c else None,
        "temperature": c.temperature if c else None,
        "metadata_json": c.metadata_json if c else None,
    } if c else None
    result = CRMOperatorReplyService.preview_reply(
        contact_dict, body.text,
        enabled=biz.crm_operator_reply_enabled,
        max_length=biz.crm_operator_reply_max_length,
        block_stopped=biz.crm_operator_reply_block_stopped,
    )
    return asdict(result)


@router.post("/contacts/{contact_id}/reply/send")
async def send_reply(
    contact_id: int, body: ReplyRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    from shared.config import get_settings
    biz = get_settings().business
    if not biz.crm_operator_reply_enabled:
        raise HTTPException(status_code=403, detail="operator_reply_disabled")
    from core.services.crm_contact_service import CRMContactService
    from core.services.crm_operator_reply_service import CRMOperatorReplyService
    c = await CRMContactService(db).get_contact(contact_id)
    if not c:
        raise HTTPException(status_code=404, detail="contact_not_found")
    contact_dict = {
        "telegram_user_id": c.telegram_user_id,
        "telegram_chat_id": c.telegram_chat_id,
        "lead_status": c.lead_status,
        "temperature": c.temperature,
        "metadata_json": c.metadata_json,
    }
    preview = CRMOperatorReplyService.preview_reply(
        contact_dict, body.text,
        enabled=True,
        max_length=biz.crm_operator_reply_max_length,
        block_stopped=biz.crm_operator_reply_block_stopped,
    )
    if not preview.allowed:
        return {"status": "blocked", "blockers": preview.blockers}
    return {"status": "sender_not_configured"}


# ── Live Inbox Summary ──────────────────────────────────────────────────────


@router.get("/inbox/live-summary")
async def live_summary(
    max_alerts: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Live inbox summary for polling-based realtime updates."""
    from dataclasses import asdict
    from datetime import datetime, timezone
    import sqlalchemy as sa
    from infrastructure.database.models.crm_contact import CRMContactModel as C
    from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService

    now = datetime.now(timezone.utc)
    stmt = sa.select(C).where(
        C.lead_status.notin_(["stopped", "lost", "won"]),
    ).order_by(C.last_message_at.desc().nullslast()).limit(200)
    rows = (await db.execute(stmt)).scalars().all()
    contacts = []
    for r in rows:
        contacts.append({
            "id": r.id,
            "contact_name": r.first_name or r.username or str(r.telegram_user_id),
            "lead_status": r.lead_status,
            "temperature": r.temperature,
            "last_message_direction": getattr(r, "last_message_direction", None),
            "last_message_at": r.last_message_at.isoformat() if r.last_message_at else None,
            "last_intent": getattr(r, "last_intent", None),
            "metadata_json": r.metadata_json if hasattr(r, "metadata_json") else None,
        })
    summary = CRMRealtimeInboxService.build_live_summary(contacts, now, max_alerts)
    return asdict(summary)
