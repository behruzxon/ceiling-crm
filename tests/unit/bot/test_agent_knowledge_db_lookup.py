"""Bot integration tests for gated DB knowledge lookup.

The helper `_maybe_answer_from_knowledge` is driven directly with fakes (flag
on/off, match/no-match/error); the placement relative to deterministic routes
and the OpenAI fallback is source-pinned (driving the full handlers end-to-end is
heavy). Offline: no network, Redis, real DB, OpenAI, Telegram.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import apps.bot.handlers.private.ai_support as ai_support
from core.services.agent_knowledge_service import KnowledgeMatch

_SRC = "apps/bot/handlers/private/ai_support.py"


def _src() -> str:
    return Path(_SRC).read_text(encoding="utf-8")


class _Msg:
    def __init__(self, text: str = "qaysi xonaga qaysi potolok mos") -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=7, first_name="T")
        self.chat = SimpleNamespace(id=99, type="private")
        self.bot = SimpleNamespace()
        self.answers: list[str] = []

    async def answer(self, text: str, **kw: object) -> None:
        self.answers.append(text)


class _Cfg:
    def __init__(self, enabled=False, min_score=0.75, limit=5, max_chars=1200):
        self.agent_knowledge_db_lookup_enabled = enabled
        self.agent_knowledge_db_lookup_min_score = min_score
        self.agent_knowledge_db_lookup_limit = limit
        self.agent_knowledge_db_lookup_max_answer_chars = max_chars


def _patch_settings(monkeypatch, cfg):
    monkeypatch.setattr(ai_support, "get_settings", lambda: SimpleNamespace(business=cfg))


def _patch_factory(monkeypatch):
    # The helper opens a session via get_session_factory(); give it a dummy
    # async-context session (find_best is monkeypatched, so it is never used).
    class _Sess:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(ai_support, "get_session_factory", lambda: (lambda: _Sess()))


# ── Flag OFF → no lookup ─────────────────────────────────────────────────────


class TestFlagOff:
    async def test_returns_false_when_off(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=False))
        called = []

        async def _find(*a, **k):
            called.append(1)
            return None

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _find
        )
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is False
        assert msg.answers == []
        assert called == []  # find_best never invoked when flag off

    async def test_default_settings_off(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings().agent_knowledge_db_lookup_enabled is False


# ── Flag ON + match ──────────────────────────────────────────────────────────


class TestFlagOnMatch:
    async def test_match_replies_and_returns_true(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))
        _patch_factory(monkeypatch)

        async def _find(*a, **k):
            return KnowledgeMatch(
                item={"id": 3, "answer": "Yotoqxona uchun matoviy mos"}, score=1.0
            )

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _find
        )
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is True
        assert len(msg.answers) == 1
        assert "Yotoqxona uchun matoviy mos" in msg.answers[0]

    async def test_match_includes_cta(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))
        _patch_factory(monkeypatch)

        async def _find(*a, **k):
            return KnowledgeMatch(item={"id": 1, "answer": "javob"}, score=0.9)

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _find
        )
        msg = _Msg()
        await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert "Yana savolingiz bo'lsa" in msg.answers[0]

    async def test_empty_answer_falls_through(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))
        _patch_factory(monkeypatch)

        async def _find(*a, **k):
            return KnowledgeMatch(item={"id": 1, "answer": ""}, score=1.0)

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _find
        )
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is False
        assert msg.answers == []


# ── Flag ON + no match / error ───────────────────────────────────────────────


class TestFlagOnNoMatchOrError:
    async def test_no_match_returns_false(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))
        _patch_factory(monkeypatch)

        async def _find(*a, **k):
            return None

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _find
        )
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is False
        assert msg.answers == []

    async def test_lookup_error_returns_false(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))
        _patch_factory(monkeypatch)

        async def _boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(
            "core.services.agent_knowledge_service.find_best_knowledge_answer", _boom
        )
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is False  # never raises; caller continues normal flow
        assert msg.answers == []

    async def test_factory_error_returns_false(self, monkeypatch):
        _patch_settings(monkeypatch, _Cfg(enabled=True))

        def _boom_factory():
            raise RuntimeError("no factory")

        monkeypatch.setattr(ai_support, "get_session_factory", _boom_factory)
        msg = _Msg()
        out = await ai_support._maybe_answer_from_knowledge(msg, 7, msg.text)
        assert out is False


# ── Source-pin: placement after deterministic routes, before OpenAI ──────────


class TestPlacement:
    def test_helper_defined(self):
        assert "async def _maybe_answer_from_knowledge" in _src()

    def test_wired_in_both_handlers(self):
        assert _src().count("if await _maybe_answer_from_knowledge(message, user_id, text):") == 2

    def test_lookup_before_call_ai(self):
        s = _src()
        assert s.index("_maybe_answer_from_knowledge") < s.index("result = await _call_ai")

    def test_lookup_after_rate_limit(self):
        s = _src()
        assert s.index("_check_ai_rate_limit") < s.index(
            "if await _maybe_answer_from_knowledge(message, user_id, text):"
        )

    def test_lookup_after_safety_guard(self):
        s = s2 = _src()
        assert s.index("_maybe_block_stop_or_safety") < s2.index(
            "if await _maybe_answer_from_knowledge(message, user_id, text):"
        )

    def test_lookup_after_operator_route(self):
        s = _src()
        assert s.index("_try_operator_handoff") < s.index(
            "if await _maybe_answer_from_knowledge(message, user_id, text):"
        )

    def test_lookup_after_price_route(self):
        s = _src()
        assert s.index("_is_price_query") < s.index(
            "if await _maybe_answer_from_knowledge(message, user_id, text):"
        )

    def test_lookup_after_catalog_route(self):
        s = _src()
        assert s.index("_is_catalog_request") < s.index(
            "if await _maybe_answer_from_knowledge(message, user_id, text):"
        )

    def test_lookup_returns_on_match(self):
        # the wired call returns immediately on True (skips OpenAI)
        s = _src()
        idx = s.index("if await _maybe_answer_from_knowledge(message, user_id, text):")
        assert "return" in s[idx : idx + 80]

    def test_helper_gated_on_flag(self):
        s = _src()
        assert "agent_knowledge_db_lookup_enabled" in s

    def test_helper_never_raises(self):
        s = _src()
        idx = s.index("async def _maybe_answer_from_knowledge")
        body = s[idx : idx + 2400]
        assert "try:" in body and "except Exception" in body

    def test_helper_logs_match_and_failure(self):
        s = _src()
        assert "agent_knowledge_db_match" in s
        assert "agent_knowledge_db_lookup_failed" in s


# ── Unchanged-behavior pins (deterministic routes still win) ─────────────────


class TestDeterministicRoutesUnchanged:
    def test_safety_guard_intact(self):
        assert "_maybe_block_stop_or_safety(message, state, user_id, text)" in _src()

    def test_price_route_intact(self):
        assert "_is_price_query(text)" in _src()

    def test_catalog_route_intact(self):
        assert "_is_catalog_request(text)" in _src()

    def test_operator_route_intact(self):
        assert "_try_operator_handoff(" in _src()

    def test_openai_capture_intact(self):
        assert _src().count('reason="openai_error"') == 2

    def test_no_unknown_capture_in_helper(self):
        # The KB helper must not schedule an unknown-question capture (a KB answer
        # is a success, not a failure).
        s = _src()
        idx = s.index("async def _maybe_answer_from_knowledge")
        body = s[idx : idx + 2400]
        assert "_schedule_unknown_capture" not in body


# ── No secrets in logs ───────────────────────────────────────────────────────


class TestLogSafety:
    def test_match_log_has_no_text(self):
        # the success log records user_id / item_id / score only — never the
        # query text or the answer.
        s = _src()
        idx = s.index('"agent_knowledge_db_match"')
        snippet = s[idx : idx + 200]
        assert "text=" not in snippet
        assert "answer=" not in snippet


# ── Reaction + dispatcher regression ─────────────────────────────────────────


class TestNoRegression:
    def test_reaction_helper_still_wired(self):
        s = _src()
        assert s.count("maybe_react_processing(message.bot, message)") == 2

    def test_imports_smoke(self):
        assert ai_support.router is not None
        assert callable(ai_support._maybe_answer_from_knowledge)
