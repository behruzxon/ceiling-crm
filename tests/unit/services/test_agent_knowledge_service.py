"""Tests for the Knowledge Base service (CRUD + promote-to-FAQ).

Pure validation/sanitization/secret-rejection is tested directly; the async DB
operations are tested with a configurable fake session (no real DB needed — the
BigInteger Identity PK does not autoincrement on SQLite). Offline: no network,
Redis, real DB, OpenAI, Telegram.
"""

from __future__ import annotations

import pytest

from core.services import agent_knowledge_service as kb
from core.services.agent_knowledge_service import (
    CATEGORIES,
    LANGUAGES,
    MAX_ANSWER_LEN,
    MAX_QUESTION_LEN,
    MAX_TITLE_LEN,
    SOURCES,
    STATUSES,
    KnowledgeValidationError,
    build_knowledge_payload,
    contains_forbidden_secret,
    render_knowledge_preview,
    sanitize_knowledge_text,
    validate_knowledge_item,
)
from infrastructure.database.models.agent_knowledge_item import AgentKnowledgeItemModel
from infrastructure.database.models.agent_unknown_question import AgentUnknownQuestionModel

# ── Fake async session ───────────────────────────────────────────────────────


class _Result:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return self

    def all(self):
        return self._many


class _FakeSession:
    def __init__(self, *, one=None, many=None):
        self._result = _Result(one=one, many=many)
        self.added: list = []
        self.commits = 0

    async def execute(self, *a, **k):
        return self._result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1


def _mk_item(**kw) -> AgentKnowledgeItemModel:
    base = dict(
        id=5,
        title="t",
        question="q",
        answer="a",
        category="faq",
        language="uz",
        status="draft",
        source="manual",
        source_unknown_question_id=None,
        aliases_json=None,
        tags_json=None,
        priority=100,
        created_by="admin",
        updated_by="admin",
        approved_by=None,
        approved_at=None,
        created_at=None,
        updated_at=None,
        metadata_json=None,
    )
    base.update(kw)
    return AgentKnowledgeItemModel(**base)


# ── Vocabularies ─────────────────────────────────────────────────────────────


class TestVocabularies:
    def test_categories(self):
        assert {
            "faq",
            "price",
            "catalog",
            "warranty",
            "objection",
            "service_area",
            "process",
            "other",
        } == set(CATEGORIES)

    def test_statuses(self):
        assert {"draft", "active", "archived"} == set(STATUSES)

    def test_sources(self):
        assert {"manual", "unknown_question", "import"} == set(SOURCES)

    def test_languages(self):
        assert {"uz", "ru", "en"} == set(LANGUAGES)


# ── Secret detection ─────────────────────────────────────────────────────────


class TestForbiddenSecret:
    @pytest.mark.parametrize(
        "txt",
        [
            "key sk-ABCD1234EFGH5678",
            "bot 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
            "Authorization Bearer abcdef1234567890",
            "BOT_TOKEN=123456789:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "api_key: SUPERSECRET12345",
            "OPENAI_API_KEY=sk-aaaabbbbcccc",
            "DATABASE_URL=postgres://u:p@h/db",
            "postgresql+asyncpg://u:p@h:5432/db",
            "password=hunter2hunter",
        ],
    )
    def test_detects_secret(self, txt):
        assert contains_forbidden_secret(txt) is True

    @pytest.mark.parametrize(
        "txt",
        [
            "gulli shiftlar narxi 15 yil kafolat",
            "balkon uchun dizayn bormi",
            "",
            None,
            "narx 130000 so'm",
            "20 m2 uchun hisob",
        ],
    )
    def test_clean_text_ok(self, txt):
        assert contains_forbidden_secret(txt) is False


# ── Sanitize ─────────────────────────────────────────────────────────────────


class TestSanitize:
    def test_masks_phone(self):
        assert "+998901234567" not in sanitize_knowledge_text("tel +998901234567 ber")

    def test_collapses_whitespace(self):
        assert sanitize_knowledge_text("a   b\n\nc") == "a b c"

    def test_strips(self):
        assert sanitize_knowledge_text("  hello  ") == "hello"

    def test_empty(self):
        assert sanitize_knowledge_text("") == ""
        assert sanitize_knowledge_text(None) == ""

    def test_truncates(self):
        assert len(sanitize_knowledge_text("a" * 500, max_length=50)) <= 50

    def test_unicode_preserved(self):
        assert "гулли" in sanitize_knowledge_text("гулли shift").lower()


# ── Validate ─────────────────────────────────────────────────────────────────


class TestValidate:
    def test_valid_active(self):
        v = validate_knowledge_item(
            title="t", question="q", answer="a", category="faq", status="active", language="uz"
        )
        assert v.ok is True

    def test_active_requires_question(self):
        v = validate_knowledge_item(
            title="", question="", answer="a", category="faq", status="active", language="uz"
        )
        assert v.ok is False

    def test_active_requires_answer(self):
        v = validate_knowledge_item(
            title="", question="q", answer="", category="faq", status="active", language="uz"
        )
        assert v.ok is False

    def test_draft_can_be_incomplete(self):
        v = validate_knowledge_item(
            title="", question="q", answer="", category="faq", status="draft", language="uz"
        )
        assert v.ok is True

    def test_bad_category(self):
        v = validate_knowledge_item(
            title="t", question="q", answer="a", category="zzz", status="draft", language="uz"
        )
        assert v.ok is False

    def test_bad_status(self):
        v = validate_knowledge_item(
            title="t", question="q", answer="a", category="faq", status="zzz", language="uz"
        )
        assert v.ok is False

    def test_bad_language(self):
        v = validate_knowledge_item(
            title="t", question="q", answer="a", category="faq", status="draft", language="zz"
        )
        assert v.ok is False

    def test_secret_in_answer_invalid(self):
        v = validate_knowledge_item(
            title="t",
            question="q",
            answer="key sk-ABCDEFGH1234",
            category="faq",
            status="draft",
            language="uz",
        )
        assert v.ok is False

    def test_title_too_long(self):
        v = validate_knowledge_item(
            title="x" * (MAX_TITLE_LEN + 1),
            question="q",
            answer="a",
            category="faq",
            status="draft",
            language="uz",
        )
        assert v.ok is False

    def test_question_too_long(self):
        v = validate_knowledge_item(
            title="t",
            question="x" * (MAX_QUESTION_LEN + 1),
            answer="a",
            category="faq",
            status="draft",
            language="uz",
        )
        assert v.ok is False

    def test_answer_too_long(self):
        v = validate_knowledge_item(
            title="t",
            question="q",
            answer="x" * (MAX_ANSWER_LEN + 1),
            category="faq",
            status="draft",
            language="uz",
        )
        assert v.ok is False

    def test_warning_when_answer_empty_with_question(self):
        v = validate_knowledge_item(
            title="t", question="q", answer="", category="faq", status="draft", language="uz"
        )
        assert v.ok is True
        assert v.warnings


# ── build_knowledge_payload ──────────────────────────────────────────────────


class TestBuildPayload:
    def test_basic_draft(self):
        p = build_knowledge_payload(question="q", answer="a")
        assert p["status"] == "draft" and p["category"] == "faq" and p["language"] == "uz"

    def test_bad_category_coerced(self):
        p = build_knowledge_payload(question="q", category="zzz")
        assert p["category"] == "faq"

    def test_bad_status_coerced(self):
        p = build_knowledge_payload(question="q", status="zzz")
        assert p["status"] == "draft"

    def test_bad_language_coerced(self):
        p = build_knowledge_payload(question="q", language="zz")
        assert p["language"] == "uz"

    def test_bad_source_coerced(self):
        p = build_knowledge_payload(question="q", source="zzz")
        assert p["source"] == "manual"

    def test_phone_masked_in_payload(self):
        p = build_knowledge_payload(question="tel +998901234567", answer="a")
        assert "+998901234567" not in p["question"]

    @pytest.mark.parametrize(
        "secret",
        [
            "key sk-ABCD1234EFGH",
            "bot 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
            "DATABASE_URL=postgres://u:p@h/db",
            "Bearer abcdef1234567",
        ],
    )
    def test_secret_in_answer_raises(self, secret):
        with pytest.raises(KnowledgeValidationError):
            build_knowledge_payload(question="q", answer=secret, status="active")

    def test_secret_in_question_raises(self):
        with pytest.raises(KnowledgeValidationError):
            build_knowledge_payload(question="sk-ABCDEFGH1234", answer="a")

    def test_active_without_answer_raises(self):
        with pytest.raises(KnowledgeValidationError):
            build_knowledge_payload(question="q", answer="", status="active")

    def test_active_sets_no_approved_in_payload_only(self):
        # build_knowledge_payload does not stamp approved_* (the DB layer does).
        p = build_knowledge_payload(question="q", answer="a", status="active")
        assert "approved_at" not in p

    def test_actor_stamped(self):
        p = build_knowledge_payload(question="q", actor="boss")
        assert p["created_by"] == "boss" and p["updated_by"] == "boss"

    def test_aliases_from_csv(self):
        p = build_knowledge_payload(question="q", aliases="a, b ,c")
        assert p["aliases_json"] == ["a", "b", "c"]

    def test_aliases_from_list(self):
        p = build_knowledge_payload(question="q", aliases=["x", "y"])
        assert p["aliases_json"] == ["x", "y"]

    def test_aliases_empty_is_none(self):
        p = build_knowledge_payload(question="q", aliases="")
        assert p["aliases_json"] is None

    def test_tags_normalized(self):
        p = build_knowledge_payload(question="q", tags="t1,t2")
        assert p["tags_json"] == ["t1", "t2"]

    def test_priority_default(self):
        p = build_knowledge_payload(question="q")
        assert p["priority"] == 100

    def test_priority_bad_falls_back(self):
        p = build_knowledge_payload(question="q", priority="high")
        assert p["priority"] == 100

    def test_source_unknown_question_link(self):
        p = build_knowledge_payload(
            question="q", source="unknown_question", source_unknown_question_id=42
        )
        assert p["source"] == "unknown_question" and p["source_unknown_question_id"] == 42


# ── render_preview ───────────────────────────────────────────────────────────


class TestRenderPreview:
    def test_with_answer(self):
        assert render_knowledge_preview("q", "a") == "q → a"

    def test_question_only(self):
        assert render_knowledge_preview("q", "") == "q"

    def test_truncates(self):
        assert len(render_knowledge_preview("x" * 200, "y" * 200, width=50)) <= 50

    def test_masks_phone(self):
        assert "+998901234567" not in render_knowledge_preview("tel +998901234567", "ok")


# ── Async DB ops (fake session) ──────────────────────────────────────────────


class TestCreate:
    async def test_create_draft_returns_dict(self):
        s = _FakeSession()
        out = await kb.create_knowledge_item(s, question="q", answer="a", status="draft")
        assert out["status"] == "draft"
        assert s.commits == 1 and len(s.added) == 1

    async def test_create_active_stamps_approved(self):
        s = _FakeSession()
        out = await kb.create_knowledge_item(
            s, question="q", answer="a", status="active", actor="boss"
        )
        assert out["status"] == "active"
        assert out["approved_by"] == "boss" and out["approved_at"] is not None

    async def test_create_secret_raises(self):
        s = _FakeSession()
        with pytest.raises(KnowledgeValidationError):
            await kb.create_knowledge_item(
                s, question="q", answer="sk-ABCDEFGH1234", status="active"
            )
        assert s.commits == 0

    async def test_create_active_without_answer_raises(self):
        s = _FakeSession()
        with pytest.raises(KnowledgeValidationError):
            await kb.create_knowledge_item(s, question="q", answer="", status="active")


class TestUpdate:
    async def test_update_changes_fields(self):
        s = _FakeSession(one=_mk_item(status="draft"))
        out = await kb.update_knowledge_item(s, 5, answer="new answer", actor="boss")
        assert out["answer"] == "new answer"
        assert s.commits == 1

    async def test_update_not_found_returns_none(self):
        s = _FakeSession(one=None)
        out = await kb.update_knowledge_item(s, 999, answer="x")
        assert out is None

    async def test_update_to_active_without_answer_raises(self):
        s = _FakeSession(one=_mk_item(status="draft", answer=""))
        with pytest.raises(KnowledgeValidationError):
            await kb.update_knowledge_item(s, 5, status="active")

    async def test_update_secret_raises(self):
        s = _FakeSession(one=_mk_item())
        with pytest.raises(KnowledgeValidationError):
            await kb.update_knowledge_item(
                s, 5, answer="bot 123456789:ABCDEFGHIJKLMNOPQRSTUV012345"
            )

    async def test_update_activate_stamps_approved(self):
        s = _FakeSession(one=_mk_item(status="draft", question="q", answer="a", approved_at=None))
        out = await kb.update_knowledge_item(s, 5, status="active", actor="boss")
        assert out["status"] == "active" and out["approved_by"] == "boss"

    async def test_update_aliases_explicit(self):
        s = _FakeSession(one=_mk_item())
        out = await kb.update_knowledge_item(s, 5, aliases="x,y")
        assert out["aliases"] == ["x", "y"]

    async def test_update_phone_masked(self):
        s = _FakeSession(one=_mk_item())
        out = await kb.update_knowledge_item(s, 5, answer="tel +998901234567")
        assert "+998901234567" not in out["answer"]


class TestArchive:
    async def test_archive_sets_status(self):
        s = _FakeSession(one=_mk_item(status="active"))
        out = await kb.archive_knowledge_item(s, 5, actor="boss")
        assert out["status"] == "archived"

    async def test_archive_not_found(self):
        s = _FakeSession(one=None)
        assert await kb.archive_knowledge_item(s, 999) is None


class TestListGet:
    async def test_list_returns_dicts(self):
        s = _FakeSession(many=[_mk_item(id=1), _mk_item(id=2)])
        out = await kb.list_knowledge_items(s)
        assert len(out) == 2 and out[0]["id"] == 1

    async def test_get_found(self):
        s = _FakeSession(one=_mk_item(id=7))
        out = await kb.get_knowledge_item(s, 7)
        assert out["id"] == 7

    async def test_get_not_found(self):
        s = _FakeSession(one=None)
        assert await kb.get_knowledge_item(s, 999) is None


class TestPromote:
    async def test_promote_creates_item_and_marks_converted(self):
        uq = AgentUnknownQuestionModel(
            id=10,
            original_text_preview="balkon narxi qancha",
            status="new",
            reason="no_catalog_match",
        )
        s = _FakeSession(one=uq)
        out = await kb.promote_unknown_question_to_faq(
            s, 10, answer="Balkon uchun maxsus narx", status="draft", actor="boss"
        )
        assert out["source"] == "unknown_question"
        assert out["source_unknown_question_id"] == 10
        assert uq.status == "converted_to_faq"
        assert s.commits == 1

    async def test_promote_prefills_question_from_preview(self):
        uq = AgentUnknownQuestionModel(
            id=11,
            original_text_preview="hammom shift bormi",
            status="reviewed",
            reason="no_catalog_match",
        )
        s = _FakeSession(one=uq)
        out = await kb.promote_unknown_question_to_faq(s, 11, answer="Ha bor")
        assert out["question"] == "hammom shift bormi"

    async def test_promote_explicit_question_overrides(self):
        uq = AgentUnknownQuestionModel(
            id=12, original_text_preview="x", status="new", reason="ai_fallback"
        )
        s = _FakeSession(one=uq)
        out = await kb.promote_unknown_question_to_faq(
            s, 12, question="Better question", answer="a"
        )
        assert out["question"] == "Better question"

    async def test_promote_unknown_not_found_raises(self):
        s = _FakeSession(one=None)
        with pytest.raises(LookupError):
            await kb.promote_unknown_question_to_faq(s, 999, answer="a")

    async def test_promote_secret_answer_raises(self):
        uq = AgentUnknownQuestionModel(
            id=13, original_text_preview="q", status="new", reason="ai_fallback"
        )
        s = _FakeSession(one=uq)
        with pytest.raises(KnowledgeValidationError):
            await kb.promote_unknown_question_to_faq(
                s, 13, answer="sk-ABCDEFGH1234", status="active"
            )

    async def test_promote_active_without_answer_raises(self):
        uq = AgentUnknownQuestionModel(
            id=14, original_text_preview="q", status="new", reason="ai_fallback"
        )
        s = _FakeSession(one=uq)
        with pytest.raises(KnowledgeValidationError):
            await kb.promote_unknown_question_to_faq(s, 14, answer="", status="active")

    async def test_promote_draft_without_answer_ok(self):
        uq = AgentUnknownQuestionModel(
            id=15, original_text_preview="q", status="new", reason="ai_fallback"
        )
        s = _FakeSession(one=uq)
        out = await kb.promote_unknown_question_to_faq(s, 15, answer="", status="draft")
        assert out["status"] == "draft"
        assert uq.status == "converted_to_faq"
