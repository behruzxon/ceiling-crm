"""Knowledge Base CRUD API — admin-editable FAQ / knowledge items.

Endpoints (all behind ``require_api_token``):

* ``GET    /api/v1/admin/agent/knowledge``           — filtered list
* ``GET    /api/v1/admin/agent/knowledge/{id}``      — detail
* ``POST   /api/v1/admin/agent/knowledge``           — create
* ``PATCH  /api/v1/admin/agent/knowledge/{id}``      — update
* ``POST   /api/v1/admin/agent/knowledge/{id}/archive`` — archive

Safety: no Telegram send, no model call, no bot behaviour change. Content with a
forbidden secret (token/key/DB URL/Bearer) is rejected with HTTP 422. The bot
does NOT read these items in this sprint (see doc 156).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies.auth import require_api_token
from core.services import agent_knowledge_service as kb
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/agent/knowledge",
    tags=["agent-knowledge"],
    dependencies=[Depends(require_api_token)],
)


@router.get("")
async def list_knowledge(
    status: str = Query(default="", max_length=20),
    category: str = Query(default="", max_length=30),
    language: str = Query(default="", max_length=8),
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> dict:
    items = await kb.list_knowledge_items(
        db,
        status=status,
        category=category,
        language=language,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items)}


@router.get("/summary")
async def knowledge_summary(db=Depends(get_db)) -> dict:
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    counts = await db.execute(
        sa.select(
            sa.func.count().label("total"),
            sa.func.count().filter(AgentKnowledgeItemModel.status == "active").label("active"),
            sa.func.count().filter(AgentKnowledgeItemModel.status == "draft").label("draft"),
            sa.func.count().filter(AgentKnowledgeItemModel.status == "archived").label("archived"),
        ).select_from(AgentKnowledgeItemModel)
    )
    row = counts.one()
    cat_res = await db.execute(
        sa.select(AgentKnowledgeItemModel.category, sa.func.count().label("cnt"))
        .group_by(AgentKnowledgeItemModel.category)
        .order_by(sa.desc("cnt"))
    )
    categories = [{"category": r.category, "count": r.cnt} for r in cat_res]
    return {
        "total": row.total,
        "active": row.active,
        "draft": row.draft,
        "archived": row.archived,
        "categories": categories,
    }


@router.get("/{item_id}")
async def get_knowledge(item_id: int, db=Depends(get_db)) -> dict:
    item = await kb.get_knowledge_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.post("")
async def create_knowledge(body: dict | None = None, db=Depends(get_db)) -> dict:
    body = body or {}
    try:
        return await kb.create_knowledge_item(
            db,
            title=body.get("title"),
            question=body.get("question"),
            answer=body.get("answer"),
            category=body.get("category", "faq"),
            status=body.get("status", "draft"),
            language=body.get("language", "uz"),
            aliases=body.get("aliases"),
            tags=body.get("tags"),
            priority=body.get("priority", 100),
            actor=body.get("actor") or "admin",
        )
    except kb.KnowledgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{item_id}")
async def update_knowledge(item_id: int, body: dict | None = None, db=Depends(get_db)) -> dict:
    body = body or {}
    fields = {
        k: body[k]
        for k in ("title", "question", "answer", "category", "status", "language", "priority")
        if k in body
    }
    extra: dict = {}
    if "aliases" in body:
        extra["aliases"] = body["aliases"]
    if "tags" in body:
        extra["tags"] = body["tags"]
    try:
        item = await kb.update_knowledge_item(
            db, item_id, actor=body.get("actor") or "admin", **extra, **fields
        )
    except kb.KnowledgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.post("/{item_id}/archive")
async def archive_knowledge(item_id: int, body: dict | None = None, db=Depends(get_db)) -> dict:
    item = await kb.archive_knowledge_item(db, item_id, actor=(body or {}).get("actor") or "admin")
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item
