"""Tests for the Operator Send-from-Web service.

Pure validation/sanitization tested directly; async orchestration uses a fake
session + injected sender (no real Telegram). Offline: no network, real DB,
OpenAI, Telegram.
"""

from __future__ import annotations

import pytest

from core.services import operator_reply_service as ors
from core.services.operator_reply_service import (
    OperatorReplyValidation,
    block_when_disabled,
    resolve_chat_target,
    sanitize_operator_reply,
    send_operator_reply,
    validate_operator_reply,
)

_CONTACT = {"id": 1, "telegram_chat_id": 55, "telegram_user_id": 55, "lead_status": "active"}


# ── Fake session ─────────────────────────────────────────────────────────────


class _FakeSession:
    def __init__(self):
        self.added: list = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass


@pytest.fixture(autouse=True)
def _no_record_outbound(monkeypatch):
    # Avoid touching CRMMessageService DB internals on the 'sent' path.
    async def _fake(self, **kw):
        return None

    import core.services.crm_message_service as cms

    monkeypatch.setattr(cms.CRMMessageService, "record_outbound", _fake)


# ── sanitize ─────────────────────────────────────────────────────────────────


class TestSanitize:
    def test_masks_phone(self):
        assert "+998901234567" not in sanitize_operator_reply("tel +998901234567")

    def test_collapses_ws(self):
        assert sanitize_operator_reply("a   b\n\nc") == "a b c"

    def test_empty(self):
        assert sanitize_operator_reply("") == ""
        assert sanitize_operator_reply(None) == ""

    def test_strips(self):
        assert sanitize_operator_reply("  hi  ") == "hi"


# ── resolve_chat_target ──────────────────────────────────────────────────────


class TestChatTarget:
    def test_prefers_chat_id(self):
        assert resolve_chat_target({"telegram_chat_id": 1, "telegram_user_id": 2}) == 1

    def test_falls_back_to_user_id(self):
        assert resolve_chat_target({"telegram_chat_id": None, "telegram_user_id": 2}) == 2

    def test_none_when_missing(self):
        assert resolve_chat_target({"telegram_chat_id": None, "telegram_user_id": None}) is None

    def test_none_contact(self):
        assert resolve_chat_target(None) is None


# ── block_when_disabled ──────────────────────────────────────────────────────


class TestBlockWhenDisabled:
    def test_blocks_when_off(self):
        assert block_when_disabled(False) is True

    def test_allows_when_on(self):
        assert block_when_disabled(True) is False


# ── validate ─────────────────────────────────────────────────────────────────


class TestValidate:
    def test_valid(self):
        v = validate_operator_reply("salom mijoz", contact=_CONTACT)
        assert v.ok is True and v.blockers == ()

    def test_empty_blocked(self):
        assert "empty_text" in validate_operator_reply("", contact=_CONTACT).blockers

    def test_whitespace_only_blocked(self):
        assert "empty_text" in validate_operator_reply("   ", contact=_CONTACT).blockers

    def test_too_long_blocked(self):
        v = validate_operator_reply("x" * 1001, contact=_CONTACT, max_chars=1000)
        assert "text_too_long" in v.blockers

    def test_custom_max_chars(self):
        assert (
            "text_too_long"
            in validate_operator_reply("hello", contact=_CONTACT, max_chars=3).blockers
        )

    @pytest.mark.parametrize(
        "secret",
        [
            "key sk-ABCDEFGH1234",
            "bot 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
            "Bearer abcdef1234567",
            "api_key: SUPERSECRET12345",
        ],
    )
    def test_secret_blocked(self, secret):
        assert "secret_blocked" in validate_operator_reply(secret, contact=_CONTACT).blockers

    def test_contact_not_found(self):
        assert "contact_not_found" in validate_operator_reply("hi there", contact=None).blockers

    def test_missing_chat_id(self):
        v = validate_operator_reply(
            "hi there", contact={"id": 1, "telegram_chat_id": None, "telegram_user_id": None}
        )
        assert "missing_chat_id" in v.blockers

    @pytest.mark.parametrize("status", ["stopped", "lost"])
    def test_stopped_blocked(self, status):
        v = validate_operator_reply(
            "hi there", contact={"id": 1, "telegram_chat_id": 5, "lead_status": status}
        )
        assert "contact_stopped" in v.blockers

    def test_stopped_allowed_when_block_off(self):
        v = validate_operator_reply(
            "hi there",
            contact={"id": 1, "telegram_chat_id": 5, "lead_status": "stopped"},
            block_stopped=False,
        )
        assert "contact_stopped" not in v.blockers

    def test_phone_warning(self):
        v = validate_operator_reply("call +998901234567 please", contact=_CONTACT)
        assert "contains_phone" in v.warnings

    def test_preview_masks_phone(self):
        v = validate_operator_reply("call +998901234567", contact=_CONTACT)
        assert "+998901234567" not in v.preview

    def test_message_hash_stable(self):
        a = validate_operator_reply("hello there", contact=_CONTACT).message_hash
        b = validate_operator_reply("hello there", contact=_CONTACT).message_hash
        assert a == b and len(a) == 64

    def test_validation_dataclass_shape(self):
        v = validate_operator_reply("hi there", contact=_CONTACT)
        assert isinstance(v, OperatorReplyValidation)


# ── send orchestration ───────────────────────────────────────────────────────


async def _good_sender(chat_id, text):
    return True, 9001, None


async def _bad_sender(chat_id, text):
    return False, None, "TelegramForbiddenError"


class TestSendDisabled:
    async def test_flag_off_returns_sender_disabled(self):
        s = _FakeSession()
        r = await send_operator_reply(s, contact=_CONTACT, text="salom mijoz", enabled=False)
        assert r["status"] == "sender_disabled"

    async def test_flag_off_no_send_called(self):
        s = _FakeSession()
        called = []

        async def _sender(c, t):
            called.append(1)
            return True, 1, None

        await send_operator_reply(
            s, contact=_CONTACT, text="salom mijoz", enabled=False, sender=_sender
        )
        assert called == []  # sender never invoked when disabled

    async def test_flag_off_records_blocked_audit(self):
        s = _FakeSession()
        await send_operator_reply(s, contact=_CONTACT, text="salom mijoz", enabled=False)
        assert len(s.added) == 1  # one audit row (status blocked, reason sender_disabled)


class TestSendBlockedValidation:
    async def test_empty_blocked(self):
        s = _FakeSession()
        r = await send_operator_reply(s, contact=_CONTACT, text="", enabled=True, confirm_send=True)
        assert r["status"] == "blocked" and "empty_text" in r["blockers"]

    async def test_secret_blocked_no_send(self):
        s = _FakeSession()
        called = []

        async def _sender(c, t):
            called.append(1)
            return True, 1, None

        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="key sk-ABCDEFGH1234",
            enabled=True,
            confirm_send=True,
            sender=_sender,
        )
        assert r["status"] == "blocked" and called == []

    async def test_missing_chat_blocked(self):
        s = _FakeSession()
        r = await send_operator_reply(
            s,
            contact={
                "id": 1,
                "telegram_chat_id": None,
                "telegram_user_id": None,
                "lead_status": "active",
            },
            text="hi there",
            enabled=True,
            confirm_send=True,
        )
        assert r["status"] == "blocked" and "missing_chat_id" in r["blockers"]


class TestConfirmGate:
    async def test_confirm_required_no_send(self):
        s = _FakeSession()
        called = []

        async def _sender(c, t):
            called.append(1)
            return True, 1, None

        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_required=True,
            confirm_send=False,
            sender=_sender,
        )
        assert r["status"] == "confirm_required" and called == []

    async def test_confirm_not_required_sends(self):
        s = _FakeSession()
        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_required=False,
            sender=_good_sender,
        )
        assert r["status"] == "sent"


class TestSendSuccess:
    async def test_sent(self):
        s = _FakeSession()
        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_send=True,
            sender=_good_sender,
        )
        assert r["status"] == "sent" and r["telegram_message_id"] == 9001

    async def test_sent_records_audit(self):
        s = _FakeSession()
        await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_send=True,
            sender=_good_sender,
        )
        # one audit row added (record_outbound is faked away)
        assert len(s.added) == 1 and s.commits >= 1

    async def test_sent_masks_phone_in_delivery(self):
        captured = {}

        async def _sender(chat_id, text):
            captured["text"] = text
            return True, 1, None

        s = _FakeSession()
        await send_operator_reply(
            s,
            contact=_CONTACT,
            text="call +998901234567 now",
            enabled=True,
            confirm_send=True,
            sender=_sender,
        )
        assert "+998901234567" not in captured["text"]


class TestSendFailure:
    async def test_failed_status(self):
        s = _FakeSession()
        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_send=True,
            sender=_bad_sender,
        )
        assert r["status"] == "failed" and r["error"] == "TelegramForbiddenError"

    async def test_failed_records_audit(self):
        s = _FakeSession()
        await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=True,
            confirm_send=True,
            sender=_bad_sender,
        )
        assert len(s.added) == 1

    async def test_sender_exception_isolated(self):
        # A sender that raises should be caught by the default-sender contract;
        # here we simulate a sender returning a failure tuple (never raising).
        async def _raises(c, t):
            raise RuntimeError("boom")

        s = _FakeSession()
        with pytest.raises(RuntimeError):
            # our injected sender raising is the caller's contract to handle;
            # the DEFAULT sender never raises (covered separately).
            await send_operator_reply(
                s,
                contact=_CONTACT,
                text="hi there",
                enabled=True,
                confirm_send=True,
                sender=_raises,
            )


class TestNoContact:
    async def test_no_contact_blocked(self):
        s = _FakeSession()
        r = await send_operator_reply(
            s, contact=None, text="hi there", enabled=True, confirm_send=True, sender=_good_sender
        )
        assert r["status"] == "blocked"


# ── safety / no token leak ───────────────────────────────────────────────────


class TestSafety:
    def test_default_sender_never_logs_token(self):
        import inspect

        src = inspect.getsource(ors._default_sender)
        assert "get_secret_value()" in src
        assert "print(" not in src

    def test_module_no_openai(self):
        from pathlib import Path

        src = Path("core/services/operator_reply_service.py").read_text(encoding="utf-8")
        assert "import openai" not in src
        assert "AsyncOpenAI" not in src

    async def test_audit_preview_truncated_100(self):
        s = _FakeSession()
        await send_operator_reply(
            s,
            contact=_CONTACT,
            text="a " * 400,
            enabled=True,
            confirm_send=True,
            sender=_good_sender,
        )
        audit = s.added[0]
        assert len(audit.message_preview) <= 100


class TestDefaultFlag:
    def test_flag_default_off(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings().operator_web_send_enabled is False


# ── Parametrized coverage expansion ──────────────────────────────────────────


class TestValidateMatrix:
    @pytest.mark.parametrize(
        "text,ok",
        [
            ("salom hurmatli mijoz", True),
            ("narx haqida ma'lumot", True),
            ("kafolat 15 yil", True),
            ("", False),
            ("   ", False),
            ("x" * 2000, False),
        ],
    )
    def test_basic_matrix(self, text, ok):
        assert validate_operator_reply(text, contact=_CONTACT).ok is ok

    @pytest.mark.parametrize(
        "status,blocked",
        [
            ("active", False),
            ("new", False),
            ("hot", False),
            ("won", False),
            ("stopped", True),
            ("lost", True),
        ],
    )
    def test_status_matrix(self, status, blocked):
        c = {"id": 1, "telegram_chat_id": 5, "lead_status": status}
        v = validate_operator_reply("salom mijoz", contact=c)
        assert ("contact_stopped" in v.blockers) is blocked

    @pytest.mark.parametrize("uid_chat", [(None, 9), (9, None), (9, 9)])
    def test_chat_target_present_matrix(self, uid_chat):
        chat, user = uid_chat
        c = {"id": 1, "telegram_chat_id": chat, "telegram_user_id": user, "lead_status": "active"}
        assert "missing_chat_id" not in validate_operator_reply("salom mijoz", contact=c).blockers

    @pytest.mark.parametrize(
        "text",
        ["normal text", "20 m2 narx", "гулли shift", "kafolat haqida", "operatorga ulayman"],
    )
    def test_clean_texts_have_no_secret_blocker(self, text):
        assert "secret_blocked" not in validate_operator_reply(text, contact=_CONTACT).blockers


class TestSendMatrix:
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_disabled_never_sends(self, enabled):
        s = _FakeSession()
        called = []

        async def _sender(c, t):
            called.append(1)
            return True, 1, None

        r = await send_operator_reply(
            s,
            contact=_CONTACT,
            text="salom mijoz",
            enabled=enabled,
            confirm_send=True,
            sender=_sender,
        )
        if enabled:
            assert r["status"] == "sent" and called == [1]
        else:
            assert r["status"] == "sender_disabled" and called == []

    @pytest.mark.parametrize("msg_id", [1, 42, 9999, 123456789])
    async def test_message_id_recorded(self, msg_id):
        async def _sender(c, t):
            return True, msg_id, None

        s = _FakeSession()
        r = await send_operator_reply(
            s, contact=_CONTACT, text="salom mijoz", enabled=True, confirm_send=True, sender=_sender
        )
        assert r["telegram_message_id"] == msg_id

    @pytest.mark.parametrize(
        "err",
        ["TelegramForbiddenError", "TelegramBadRequest", "TelegramNetworkError", "RuntimeError"],
    )
    async def test_failure_error_types(self, err):
        async def _sender(c, t):
            return False, None, err

        s = _FakeSession()
        r = await send_operator_reply(
            s, contact=_CONTACT, text="salom mijoz", enabled=True, confirm_send=True, sender=_sender
        )
        assert r["status"] == "failed" and r["error"] == err
