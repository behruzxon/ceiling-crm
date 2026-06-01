"""
core.services.agent_knowledge_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin-editable Knowledge Base CRUD + "promote Unknown Question to FAQ".

This is the storage/edit layer for FAQ-style knowledge the business can manage
after deployment. **The bot does NOT read these items yet** (see doc 156): this
sprint is read/write for admins only, with no change to bot behaviour.

Design principles
-----------------
* **Pure-first validation/sanitization.** ``sanitize_knowledge_text`` and
  ``validate_knowledge_item`` are framework-free and trivially testable.
* **Secret-safe.** Content is sanitized (phones masked, URLs noted) and **blocked**
  outright if it contains a bot token / OpenAI key / DATABASE_URL / Bearer — those
  must never be persisted into knowledge.
* **Draft vs active.** A ``draft`` may be incomplete; an ``active`` item must have a
  non-empty question and answer within length limits.
* **No bot mutation.** Nothing here edits the system prompt or the KB markdown file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from shared.utils.phone import mask_phone_in_text

# ── Vocabularies ─────────────────────────────────────────────────────────────

CATEGORIES: frozenset[str] = frozenset(
    {
        "faq",
        "price",
        "catalog",
        "warranty",
        "objection",
        "service_area",
        "process",
        "other",
    }
)
STATUSES: frozenset[str] = frozenset({"draft", "active", "archived"})
SOURCES: frozenset[str] = frozenset({"manual", "unknown_question", "import"})
LANGUAGES: frozenset[str] = frozenset({"uz", "ru", "en"})

# Length limits (chars). Active items must fit; drafts are checked only on activate.
MAX_TITLE_LEN = 200
MAX_QUESTION_LEN = 1000
MAX_ANSWER_LEN = 4000

# ── Secret patterns (BLOCK — never store these in knowledge) ─────────────────

_RE_SK_KEY = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_RE_BOT_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_\-]{20,}\b")
_RE_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-=]{8,}")
_RE_SECRET_KV = re.compile(
    r"(?i)\b(bot_token|api[_-]?key|openai[_-]?api[_-]?key|secret|password|passwd"
    r"|database_url|db_url)\b\s*[:=]\s*\S+"
)
_RE_DB_URL = re.compile(r"(?i)\bpostg(?:res|resql)(?:\+\w+)?://\S+")
_RE_WS = re.compile(r"\s+")


class KnowledgeValidationError(ValueError):
    """Raised when a knowledge item is invalid or contains forbidden secrets."""


@dataclass(frozen=True)
class KnowledgeValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def contains_forbidden_secret(text: str | None) -> bool:
    """True if *text* contains a bot token / key / DB URL / Bearer — never store."""
    if not text:
        return False
    s = str(text)
    return bool(
        _RE_SK_KEY.search(s)
        or _RE_BOT_TOKEN.search(s)
        or _RE_BEARER.search(s)
        or _RE_SECRET_KV.search(s)
        or _RE_DB_URL.search(s)
    )


def _reject_secrets(**named_texts: str | None) -> None:
    """Raise if any named field contains a forbidden secret (checked on raw text)."""
    bad = [name for name, value in named_texts.items() if contains_forbidden_secret(value)]
    if bad:
        joined = ", ".join(sorted(bad))
        raise KnowledgeValidationError(
            f"{joined}: maxfiy ma'lumot (token/kalit/DB URL) saqlab bo'lmaydi"
        )


def sanitize_knowledge_text(text: str | None, *, max_length: int | None = None) -> str:
    """Return cleaned knowledge text: phones masked, whitespace normalized.

    This does NOT silently strip secrets — secret-bearing content is rejected by
    :func:`validate_knowledge_item` so an admin never accidentally saves a leak.
    Phones are masked defensively (knowledge should not contain personal numbers).
    """
    if not text:
        return ""
    out = mask_phone_in_text(str(text))
    out = _RE_WS.sub(" ", out).strip()
    if max_length is not None:
        out = out[:max_length]
    return out


def _norm_list(value: Any) -> list[str] | None:
    """Normalize an aliases/tags input (list or comma string) to a clean list."""
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value]
    else:
        return None
    cleaned = [p[:100] for p in parts if p]
    return cleaned or None


def validate_knowledge_item(
    *,
    title: str | None,
    question: str | None,
    answer: str | None,
    category: str,
    status: str,
    language: str = "uz",
) -> KnowledgeValidation:
    """Validate a would-be knowledge item. Pure; returns structured result.

    Rules:
    * category / status / language must be in the known vocabularies;
    * no field may contain a forbidden secret (token/key/DB URL/Bearer);
    * length limits apply to title/question/answer;
    * an ``active`` item must have a non-empty question AND answer;
    * a ``draft`` may be incomplete.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if category not in CATEGORIES:
        errors.append(f"Noma'lum kategoriya: {category}")
    if status not in STATUSES:
        errors.append(f"Noma'lum status: {status}")
    if language not in LANGUAGES:
        errors.append(f"Noma'lum til: {language}")

    for field_name, value, limit in (
        ("title", title, MAX_TITLE_LEN),
        ("question", question, MAX_QUESTION_LEN),
        ("answer", answer, MAX_ANSWER_LEN),
    ):
        if contains_forbidden_secret(value):
            errors.append(f"{field_name}: maxfiy ma'lumot (token/kalit) saqlab bo'lmaydi")
        if value is not None and len(str(value)) > limit:
            errors.append(f"{field_name}: juda uzun (maksimal {limit})")

    if status == "active":
        if not (question and question.strip()):
            errors.append("Active FAQ uchun savol majburiy")
        if not (answer and answer.strip()):
            errors.append("Active FAQ uchun javob majburiy")

    if (question and question.strip()) and not (answer and answer.strip()):
        warnings.append("Javob bo'sh — faqat draft sifatida saqlanadi")

    return KnowledgeValidation(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def build_knowledge_payload(
    *,
    title: str | None = None,
    question: str | None = None,
    answer: str | None = None,
    category: str = "faq",
    status: str = "draft",
    language: str = "uz",
    source: str = "manual",
    source_unknown_question_id: int | None = None,
    aliases: Any = None,
    tags: Any = None,
    priority: int = 100,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sanitized, validated insert payload. Raises on invalid input.

    Coerces vocab fields, sanitizes text, validates, and stamps ``created_by``.
    Raises :class:`KnowledgeValidationError` (with a joined message) if invalid.
    """
    safe_category = category if category in CATEGORIES else "faq"
    safe_status = status if status in STATUSES else "draft"
    safe_language = language if language in LANGUAGES else "uz"
    safe_source = source if source in SOURCES else "manual"

    # Check secrets on the RAW text first — sanitization (phone masking) can
    # mangle a bot token's digits and hide it from the secret detector.
    _reject_secrets(title=title, question=question, answer=answer)

    clean_title = sanitize_knowledge_text(title, max_length=MAX_TITLE_LEN)
    clean_question = sanitize_knowledge_text(question, max_length=MAX_QUESTION_LEN)
    clean_answer = sanitize_knowledge_text(answer, max_length=MAX_ANSWER_LEN)

    result = validate_knowledge_item(
        title=clean_title,
        question=clean_question,
        answer=clean_answer,
        category=safe_category,
        status=safe_status,
        language=safe_language,
    )
    if not result.ok:
        raise KnowledgeValidationError("; ".join(result.errors))

    return {
        "title": clean_title,
        "question": clean_question,
        "answer": clean_answer,
        "category": safe_category,
        "status": safe_status,
        "language": safe_language,
        "source": safe_source,
        "source_unknown_question_id": source_unknown_question_id,
        "aliases_json": _norm_list(aliases),
        "tags_json": _norm_list(tags),
        "priority": int(priority) if isinstance(priority, int) else 100,
        "created_by": (str(actor)[:50] if actor else None),
        "updated_by": (str(actor)[:50] if actor else None),
        "metadata_json": metadata or None,
    }


def render_knowledge_preview(question: str | None, answer: str | None, *, width: int = 120) -> str:
    """Short one-line preview for list views (sanitized + truncated)."""
    q = sanitize_knowledge_text(question)
    a = sanitize_knowledge_text(answer)
    line = f"{q} → {a}" if a else q
    return line[:width]


# ── DB operations (async; thin wrappers, callers own the session) ────────────


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "title": row.title,
        "question": row.question,
        "answer": row.answer,
        "category": row.category,
        "language": row.language,
        "status": row.status,
        "source": row.source,
        "source_unknown_question_id": row.source_unknown_question_id,
        "aliases": row.aliases_json,
        "tags": row.tags_json,
        "priority": row.priority,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
    }


async def create_knowledge_item(session: Any, **kwargs: Any) -> dict[str, Any]:
    """Validate + insert a knowledge item. Returns the row dict. Raises on invalid."""
    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    payload = build_knowledge_payload(**kwargs)
    if payload["status"] == "active":
        payload["approved_by"] = payload.get("updated_by")
        payload["approved_at"] = datetime.now(UTC)
    row = AgentKnowledgeItemModel(**payload)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


#: Sentinel so callers can distinguish "field not supplied" from "set to empty".
_UNSET: Any = object()


async def update_knowledge_item(
    session: Any,
    item_id: int,
    *,
    actor: str | None = None,
    aliases: Any = _UNSET,
    tags: Any = _UNSET,
    **fields: Any,
) -> dict[str, Any] | None:
    """Patch an existing item. Re-validates the merged result. Returns row dict or None.

    Only the fields present in *fields* (title/question/answer/category/status/
    language/priority) are changed; ``aliases``/``tags`` are updated only when
    explicitly provided (sentinel-guarded).
    """
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    res = await session.execute(
        sa.select(AgentKnowledgeItemModel).where(AgentKnowledgeItemModel.id == item_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None

    # Reject secrets on the RAW incoming fields before sanitization mangles them.
    _reject_secrets(**{k: v for k, v in fields.items() if k in ("title", "question", "answer")})

    merged = {
        "title": sanitize_knowledge_text(fields.get("title", row.title), max_length=MAX_TITLE_LEN),
        "question": sanitize_knowledge_text(
            fields.get("question", row.question), max_length=MAX_QUESTION_LEN
        ),
        "answer": sanitize_knowledge_text(
            fields.get("answer", row.answer), max_length=MAX_ANSWER_LEN
        ),
        "category": fields.get("category", row.category),
        "status": fields.get("status", row.status),
        "language": fields.get("language", row.language),
    }
    valid = validate_knowledge_item(**merged)
    if not valid.ok:
        raise KnowledgeValidationError("; ".join(valid.errors))

    for key, value in merged.items():
        setattr(row, key, value)
    if "priority" in fields and isinstance(fields["priority"], int):
        row.priority = fields["priority"]
    if aliases is not _UNSET:
        row.aliases_json = _norm_list(aliases)
    if tags is not _UNSET:
        row.tags_json = _norm_list(tags)
    row.updated_by = str(actor)[:50] if actor else row.updated_by
    row.updated_at = datetime.now(UTC)
    if merged["status"] == "active" and row.approved_at is None:
        row.approved_by = str(actor)[:50] if actor else None
        row.approved_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def archive_knowledge_item(
    session: Any, item_id: int, *, actor: str | None = None
) -> dict[str, Any] | None:
    """Set status=archived. Returns row dict or None if not found."""
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    res = await session.execute(
        sa.select(AgentKnowledgeItemModel).where(AgentKnowledgeItemModel.id == item_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None
    row.status = "archived"
    row.updated_by = str(actor)[:50] if actor else row.updated_by
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def list_knowledge_items(
    session: Any,
    *,
    status: str = "",
    category: str = "",
    language: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Filtered, paginated list (newest first)."""
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    query = sa.select(AgentKnowledgeItemModel).order_by(
        AgentKnowledgeItemModel.priority.asc(),
        AgentKnowledgeItemModel.created_at.desc(),
    )
    if status:
        query = query.where(AgentKnowledgeItemModel.status == status)
    if category:
        query = query.where(AgentKnowledgeItemModel.category == category)
    if language:
        query = query.where(AgentKnowledgeItemModel.language == language)
    if q:
        like = f"%{q}%"
        query = query.where(
            sa.or_(
                AgentKnowledgeItemModel.title.ilike(like),
                AgentKnowledgeItemModel.question.ilike(like),
                AgentKnowledgeItemModel.answer.ilike(like),
            )
        )
    query = query.limit(limit).offset(offset)
    res = await session.execute(query)
    return [_row_to_dict(r) for r in res.scalars().all()]


async def get_knowledge_item(session: Any, item_id: int) -> dict[str, Any] | None:
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel

    res = await session.execute(
        sa.select(AgentKnowledgeItemModel).where(AgentKnowledgeItemModel.id == item_id)
    )
    row = res.scalar_one_or_none()
    return _row_to_dict(row) if row is not None else None


async def promote_unknown_question_to_faq(
    session: Any,
    unknown_question_id: int,
    *,
    title: str | None = None,
    question: str | None = None,
    answer: str | None = None,
    category: str = "faq",
    status: str = "draft",
    aliases: Any = None,
    tags: Any = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Create a knowledge item from an Unknown Question and mark it converted.

    Within one session: insert the knowledge item (source=unknown_question, linked
    by id), then set the unknown question's status to ``converted_to_faq``. Raises
    :class:`KnowledgeValidationError` if the item is invalid (e.g. active without an
    answer, or content contains a secret). Raises ``LookupError`` if the unknown
    question does not exist.
    """
    import sqlalchemy as sa

    from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel
    from infrastructure.database.models.agent_unknown_question import (
        AgentUnknownQuestionModel,
    )

    res = await session.execute(
        sa.select(AgentUnknownQuestionModel).where(
            AgentUnknownQuestionModel.id == unknown_question_id
        )
    )
    uq = res.scalar_one_or_none()
    if uq is None:
        raise LookupError("unknown_question_not_found")

    # Pre-fill the question from the unknown preview when the admin didn't supply one.
    eff_question = question if (question and question.strip()) else (uq.original_text_preview or "")

    payload = build_knowledge_payload(
        title=title,
        question=eff_question,
        answer=answer,
        category=category,
        status=status,
        source="unknown_question",
        source_unknown_question_id=unknown_question_id,
        aliases=aliases,
        tags=tags,
        actor=actor,
    )
    if payload["status"] == "active":
        payload["approved_by"] = payload.get("updated_by")
        payload["approved_at"] = datetime.now(UTC)

    item = AgentKnowledgeItemModel(**payload)
    session.add(item)

    uq.status = "converted_to_faq"
    uq.updated_at = datetime.now(UTC)
    if actor:
        uq.reviewed_by = str(actor)[:50]
        uq.reviewed_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(item)
    return _row_to_dict(item)
