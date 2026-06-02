"""Bot-side CRM conversation capture tests.

The capture helper `_capture_crm_turn` is driven directly with a fake session
factory; wiring (3 turn points) and failure-safety are source-pinned + behavior-
tested. Offline: no network, real DB, OpenAI, Telegram.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import apps.bot.handlers.private.ai_support as ai_support

_SRC = "apps/bot/handlers/private/ai_support.py"


def _src() -> str:
    return Path(_SRC).read_text(encoding="utf-8")


# ── Fake contact/message services + session ──────────────────────────────────


class _FakeContactSvc:
    def __init__(self, session):
        pass

    async def upsert_contact(self, **kw):
        return SimpleNamespace(id=123)


class _Rec:
    def __init__(self):
        self.inbound = []
        self.outbound = []


class _FakeMsgSvc:
    _rec = _Rec()

    def __init__(self, session):
        pass

    async def record_inbound(self, *, contact_id, telegram_user_id, text):
        _FakeMsgSvc._rec.inbound.append((contact_id, telegram_user_id, text))

    async def record_outbound(self, *, contact_id, text, sender_type="bot"):
        _FakeMsgSvc._rec.outbound.append((contact_id, text, sender_type))


class _Sess:
    def __init__(self, store):
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def commit(self):
        self._store.append("commit")


@pytest.fixture
def _wire(monkeypatch):
    _FakeMsgSvc._rec = _Rec()
    commits: list = []
    monkeypatch.setattr("core.services.crm_contact_service.CRMContactService", _FakeContactSvc)
    monkeypatch.setattr("core.services.crm_message_service.CRMMessageService", _FakeMsgSvc)
    monkeypatch.setattr(ai_support, "get_session_factory", lambda: (lambda: _Sess(commits)))
    return _FakeMsgSvc._rec, commits


# ── _capture_crm_turn behavior ───────────────────────────────────────────────


class TestCaptureTurn:
    async def test_inbound_and_bot_recorded(self, _wire):
        rec, commits = _wire
        await ai_support._capture_crm_turn(
            user_id=7,
            chat_id=99,
            first_name="A",
            username="u",
            inbound_text="qaysi shift",
            bot_reply="javob",
        )
        assert rec.inbound == [(123, 7, "qaysi shift")]
        assert rec.outbound == [(123, "javob", "bot")]
        assert "commit" in commits

    async def test_inbound_only(self, _wire):
        rec, _ = _wire
        await ai_support._capture_crm_turn(
            user_id=7,
            chat_id=99,
            first_name=None,
            username=None,
            inbound_text="hello",
            bot_reply=None,
        )
        assert len(rec.inbound) == 1 and rec.outbound == []

    async def test_no_inbound_no_reply(self, _wire):
        rec, _ = _wire
        await ai_support._capture_crm_turn(
            user_id=7,
            chat_id=99,
            first_name=None,
            username=None,
            inbound_text=None,
            bot_reply=None,
        )
        assert rec.inbound == [] and rec.outbound == []

    async def test_capture_failure_swallowed(self, monkeypatch):
        # Factory raises → helper must not raise.
        monkeypatch.setattr(
            ai_support, "get_session_factory", lambda: (_ for _ in ()).throw(RuntimeError("x"))
        )
        await ai_support._capture_crm_turn(
            user_id=7,
            chat_id=99,
            first_name=None,
            username=None,
            inbound_text="hi",
            bot_reply="yo",
        )  # must not raise


# ── _schedule_crm_turn ───────────────────────────────────────────────────────


class TestScheduleTurn:
    def test_schedule_never_raises_without_loop(self, monkeypatch):
        # create_task with no running loop raises RuntimeError → must be swallowed.
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=1), from_user=SimpleNamespace(first_name="A", username="u")
        )
        ai_support._schedule_crm_turn(msg, 7, "in", "out")  # no running loop → swallowed

    async def test_schedule_creates_task(self, monkeypatch):
        captured = {}

        async def _fake_capture(**kw):
            captured.update(kw)

        monkeypatch.setattr(ai_support, "_capture_crm_turn", _fake_capture)
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=42), from_user=SimpleNamespace(first_name="B", username="bb")
        )
        ai_support._schedule_crm_turn(msg, 7, "inbound text", "bot reply")
        import asyncio

        await asyncio.sleep(0)
        assert captured.get("inbound_text") == "inbound text"
        assert captured.get("bot_reply") == "bot reply"
        assert captured.get("chat_id") == 42


# ── Source-pin: capture wiring ───────────────────────────────────────────────


class TestWiring:
    def test_helper_defined(self):
        assert "async def _capture_crm_turn" in _src()

    def test_scheduler_defined(self):
        assert "def _schedule_crm_turn" in _src()

    def test_three_turn_points(self):
        assert _src().count("_schedule_crm_turn(message, user_id, text,") == 3

    def test_capture_uses_crm_services(self):
        s = _src()
        assert "CRMContactService" in s and "CRMMessageService" in s

    def test_capture_never_raises(self):
        s = _src()
        idx = s.index("async def _capture_crm_turn")
        body = s[idx : idx + 2000]
        assert "try:" in body and "except Exception" in body

    def test_capture_logs_failure(self):
        assert "crm_conversation_capture_failed" in _src()


# ── Unchanged behaviour ──────────────────────────────────────────────────────


class TestUnchanged:
    def test_unknown_capture_intact(self):
        assert _src().count('reason="openai_error"') == 2
        assert 'reason="safety_block"' in _src()

    def test_reaction_intact(self):
        assert _src().count("maybe_react_processing(message.bot, message)") == 2

    def test_kb_lookup_intact(self):
        assert _src().count("if await _maybe_answer_from_knowledge(message, user_id, text):") == 2

    def test_capture_failure_log_has_no_message_text(self):
        # The failure log is a fixed event string with no message-text interpolation
        # (CRMMessageService.record_inbound applies redaction on the stored row).
        assert 'log.warning("crm_conversation_capture_failed", exc_info=False)' in _src()


class TestSmoke:
    def test_imports(self):
        assert callable(ai_support._capture_crm_turn)
        assert ai_support.router is not None
