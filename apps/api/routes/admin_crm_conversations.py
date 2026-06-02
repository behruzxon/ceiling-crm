"""CRM Conversation Inbox API + Operator Send-from-Web.

* ``GET  /api/v1/admin/crm/conversations``                       — conversation list
* ``GET  /api/v1/admin/crm/conversations/{contact_id}/messages`` — chronological timeline
* ``POST /api/v1/admin/crm/conversations/{contact_id}/operator-reply`` — gated send

Send is gated by ``OPERATOR_WEB_SEND_ENABLED`` (default OFF → HTTP 403
``sender_disabled``, no Telegram send). One manual message to one known contact;
no bulk, no group, no AI/auto/campaign send. Every attempt is audited. Phones are
masked in output; tokens are never returned. See doc 158.
"""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies.auth import require_api_token
from infrastructure.database.models.crm_contact import CRMContactModel
from infrastructure.database.models.crm_message import CRMMessageModel
from infrastructure.database.session import get_db
from shared.config import get_settings
from shared.utils.phone import mask_phone

router = APIRouter(
    prefix="/api/v1/admin/crm/conversations",
    tags=["crm-conversations"],
    dependencies=[Depends(require_api_token)],
)


def _msg_to_dict(m: CRMMessageModel) -> dict:
    return {
        "id": m.id,
        "direction": m.direction,
        "sender_type": m.sender_type,
        "text": m.redacted_text or m.text,
        "message_type": m.message_type,
        "telegram_message_id": m.telegram_message_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _contact_label(c: CRMContactModel) -> str:
    name = " ".join(p for p in (c.first_name, c.last_name) if p).strip()
    return name or c.username or (f"#{c.id}")


@router.get("")
async def list_conversations(
    q: str = Query(default="", max_length=100),
    status: str = Query(default="", max_length=30),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> dict:
    """Conversation list: contacts with their latest message preview (newest first)."""
    query = sa.select(CRMContactModel).order_by(
        CRMContactModel.last_message_at.desc().nullslast(),
        CRMContactModel.id.desc(),
    )
    if status:
        query = query.where(CRMContactModel.lead_status == status)
    if q:
        like = f"%{q}%"
        query = query.where(
            sa.or_(
                CRMContactModel.first_name.ilike(like),
                CRMContactModel.last_name.ilike(like),
                CRMContactModel.username.ilike(like),
                CRMContactModel.phone.ilike(like),
            )
        )
    query = query.limit(limit).offset(offset)
    contacts = (await db.execute(query)).scalars().all()

    ids = [c.id for c in contacts]
    latest: dict[int, CRMMessageModel] = {}
    if ids:
        msgs = (
            (
                await db.execute(
                    sa.select(CRMMessageModel)
                    .where(CRMMessageModel.contact_id.in_(ids))
                    .order_by(CRMMessageModel.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        for m in msgs:
            latest.setdefault(m.contact_id, m)

    items = []
    for c in contacts:
        lm = latest.get(c.id)
        items.append(
            {
                "contact_id": c.id,
                "name": _contact_label(c),
                "phone_masked": mask_phone(c.phone) if c.phone else None,
                "lead_status": c.lead_status,
                "temperature": c.temperature,
                "last_message_preview": ((lm.redacted_text or lm.text) if lm else None),
                "last_message_at": (
                    lm.created_at.isoformat()
                    if lm and lm.created_at
                    else (c.last_message_at.isoformat() if c.last_message_at else None)
                ),
                "last_sender_type": (lm.sender_type if lm else None),
            }
        )
    return {"items": items, "count": len(items)}


@router.get("/{contact_id}/messages")
async def conversation_messages(
    contact_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    db=Depends(get_db),
) -> dict:
    """Chronological message timeline (oldest first) for one contact."""
    rows = (
        (
            await db.execute(
                sa.select(CRMMessageModel)
                .where(CRMMessageModel.contact_id == contact_id)
                .order_by(CRMMessageModel.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    rows = list(reversed(rows))  # chronological for display
    return {"items": [_msg_to_dict(m) for m in rows], "count": len(rows)}


@router.post("/{contact_id}/operator-reply")
async def operator_reply(
    contact_id: int,
    body: dict | None = None,
    db=Depends(get_db),
) -> dict:
    """Send ONE manual operator reply to the client. Gated by OPERATOR_WEB_SEND_ENABLED.

    Flag OFF → 403 ``sender_disabled`` (no Telegram send). Validation failure →
    422. Confirmation required but not given → 409. Sent / failed → 200 with status.
    """
    from core.services.crm_contact_service import CRMContactService
    from core.services.operator_reply_service import send_operator_reply

    body = body or {}
    text = str(body.get("message") or body.get("text") or "")
    confirm_send = bool(body.get("confirm_send", False))
    operator = str(body.get("operator") or "admin")

    biz = get_settings().business
    contact_row = await CRMContactService(db).get_contact(contact_id)
    contact = None
    if contact_row is not None:
        contact = {
            "id": contact_row.id,
            "telegram_user_id": contact_row.telegram_user_id,
            "telegram_chat_id": contact_row.telegram_chat_id,
            "lead_status": contact_row.lead_status,
            "temperature": contact_row.temperature,
        }

    result = await send_operator_reply(
        db,
        contact=contact,
        text=text,
        enabled=bool(getattr(biz, "operator_web_send_enabled", False)),
        max_chars=int(getattr(biz, "operator_web_send_max_chars", 1000)),
        confirm_required=bool(getattr(biz, "operator_web_send_confirm_required", True)),
        confirm_send=confirm_send,
        block_stopped=bool(getattr(biz, "crm_operator_reply_block_stopped", True)),
        operator=operator,
    )

    status = result.get("status")
    if status == "sender_disabled":
        raise HTTPException(status_code=403, detail="sender_disabled")
    if status == "blocked":
        if "contact_not_found" in result.get("blockers", []):
            raise HTTPException(status_code=404, detail="contact_not_found")
        raise HTTPException(
            status_code=422, detail=",".join(result.get("blockers", [])) or "blocked"
        )
    if status == "confirm_required":
        raise HTTPException(status_code=409, detail="confirm_required")
    return result
