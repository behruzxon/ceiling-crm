"""Telegram reaction micro-UX tests.

Covers the helper (apps/bot/utils/reactions.py) behavior under the feature flag,
private-vs-group gating, clear/done modes, failure-safety, no-PII logging, the
default-OFF contract, and source-pin checks that the AI handlers wire the helper
around the OpenAI path without changing replies / routing / capture.

Offline: fake Bot/Message + monkeypatch. No network, Redis, DB, OpenAI, Telegram.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import apps.bot.utils.reactions as rx

# ── Fakes ────────────────────────────────────────────────────────────────────


class _FakeBot:
    def __init__(self, *, raise_exc: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._raise = raise_exc

    async def set_message_reaction(self, *, chat_id, message_id, reaction, **kw):
        self.calls.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                # store the emoji list as plain strings for easy assertions
                "emojis": [getattr(r, "emoji", None) for r in (reaction or [])],
                "cleared": not reaction,
            }
        )
        if self._raise is not None:
            raise self._raise
        return True


def _msg(chat_type: str = "private", chat_id: int = 10, message_id: int = 99):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        message_id=message_id,
        bot=None,
    )


class _Cfg:
    def __init__(
        self,
        enabled=False,
        groups=False,
        processing="👀",
        done="✅",
        clear_on_reply=True,
    ):
        self.reactions_enabled = enabled
        self.reactions_groups_enabled = groups
        self.reaction_processing = processing
        self.reaction_done = done
        self.reaction_clear_on_reply = clear_on_reply


def _patch_cfg(monkeypatch: pytest.MonkeyPatch, cfg: _Cfg) -> None:
    monkeypatch.setattr(rx, "_reactions_settings", lambda: cfg)


# ── Flag OFF → no-op ─────────────────────────────────────────────────────────


class TestFlagOff:
    async def test_processing_noop_when_off(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=False))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls == []

    async def test_done_noop_when_off(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=False))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert bot.calls == []

    async def test_clear_noop_when_off(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=False))
        bot = _FakeBot()
        await rx.maybe_clear_reaction(bot, _msg())
        assert bot.calls == []

    async def test_should_react_false_when_off(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=False))
        assert rx._should_react(_msg()) is False

    async def test_no_cfg_object_is_noop(self, monkeypatch):
        monkeypatch.setattr(rx, "_reactions_settings", lambda: None)
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls == []


# ── Flag ON, private chat ────────────────────────────────────────────────────


class TestPrivateEnabled:
    async def test_processing_sets_default_emoji(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert len(bot.calls) == 1
        assert bot.calls[0]["emojis"] == ["👀"]
        assert bot.calls[0]["cleared"] is False

    async def test_processing_custom_emoji_arg(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(), reaction="👍")
        assert bot.calls[0]["emojis"] == ["👍"]

    async def test_processing_uses_configured_emoji(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, processing="🔥"))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls[0]["emojis"] == ["🔥"]

    async def test_passes_chat_and_message_ids(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(chat_id=777, message_id=555))
        assert bot.calls[0]["chat_id"] == 777
        assert bot.calls[0]["message_id"] == 555

    async def test_should_react_true_private_enabled(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        assert rx._should_react(_msg()) is True


# ── Done / clear modes ───────────────────────────────────────────────────────


class TestDoneClearModes:
    async def test_done_clears_by_default(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=True))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert bot.calls[0]["cleared"] is True
        assert bot.calls[0]["emojis"] == []

    async def test_done_sets_done_emoji_when_no_clear(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False, done="✅"))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert bot.calls[0]["emojis"] == ["✅"]
        assert bot.calls[0]["cleared"] is False

    async def test_done_mode_override_clear(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg(), mode="clear")
        assert bot.calls[0]["cleared"] is True

    async def test_done_mode_override_done(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=True, done="🎉"))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg(), mode="done")
        assert bot.calls[0]["emojis"] == ["🎉"]

    async def test_clear_sends_empty_reaction(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_clear_reaction(bot, _msg())
        assert bot.calls[0]["cleared"] is True
        assert bot.calls[0]["emojis"] == []


# ── Group gating ─────────────────────────────────────────────────────────────


class TestGroupGating:
    @pytest.mark.parametrize("ctype", ["group", "supergroup"])
    async def test_group_noop_by_default(self, monkeypatch, ctype):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=False))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(chat_type=ctype))
        assert bot.calls == []

    @pytest.mark.parametrize("ctype", ["group", "supergroup"])
    async def test_group_reacts_when_groups_enabled(self, monkeypatch, ctype):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(chat_type=ctype))
        assert len(bot.calls) == 1

    async def test_group_should_react_false_by_default(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=False))
        assert rx._should_react(_msg(chat_type="group")) is False

    async def test_group_done_noop_by_default(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=False))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg(chat_type="supergroup"))
        assert bot.calls == []

    async def test_channel_chat_type_noop(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(chat_type="channel"))
        assert bot.calls == []


# ── Malformed message handling ───────────────────────────────────────────────


class TestMalformedMessage:
    async def test_none_message_noop(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, None)
        assert bot.calls == []

    async def test_no_chat_noop(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        m = SimpleNamespace(chat=None, message_id=1, bot=None)
        await rx.maybe_react_processing(bot, m)
        assert bot.calls == []

    async def test_no_message_id_noop(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        m = SimpleNamespace(chat=SimpleNamespace(id=1, type="private"), message_id=None, bot=None)
        await rx.maybe_react_processing(bot, m)
        assert bot.calls == []


# ── Failure safety (never raises) ────────────────────────────────────────────


class TestFailureSafety:
    async def test_bad_request_swallowed(self, monkeypatch):
        from aiogram.exceptions import TelegramBadRequest

        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        exc = TelegramBadRequest(method=SimpleNamespace(), message="REACTION_INVALID")
        bot = _FakeBot(raise_exc=exc)
        # must not raise
        await rx.maybe_react_processing(bot, _msg())

    async def test_forbidden_swallowed(self, monkeypatch):
        from aiogram.exceptions import TelegramForbiddenError

        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        exc = TelegramForbiddenError(method=SimpleNamespace(), message="bot was blocked")
        bot = _FakeBot(raise_exc=exc)
        await rx.maybe_react_processing(bot, _msg())

    async def test_generic_exception_swallowed(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot(raise_exc=RuntimeError("boom"))
        await rx.maybe_react_processing(bot, _msg())
        await rx.maybe_react_done(bot, _msg())
        await rx.maybe_clear_reaction(bot, _msg())

    async def test_done_failure_swallowed(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False))
        bot = _FakeBot(raise_exc=ValueError("x"))
        await rx.maybe_react_done(bot, _msg())

    async def test_clear_failure_swallowed(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot(raise_exc=ValueError("x"))
        await rx.maybe_clear_reaction(bot, _msg())


# ── No PII / secrets in logs ─────────────────────────────────────────────────


class TestNoPIIInLogs:
    async def test_logs_have_no_message_text_or_secrets(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        events: list[tuple] = []

        class _Log:
            def debug(self, event, **kw):
                events.append((event, kw))

            def warning(self, event, **kw):
                events.append((event, kw))

        monkeypatch.setattr(rx, "log", _Log())
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        await rx.maybe_clear_reaction(bot, _msg())
        assert events, "expected at least one structured log event"
        for _event, kw in events:
            # only chat_type / emoji / error_type are allowed in kwargs
            assert set(kw.keys()) <= {"chat_type", "emoji", "error_type"}
            blob = (str(kw)).lower()
            for bad in ("token", "sk-", "bot_token", "database_url", "bearer"):
                assert bad not in blob

    async def test_failure_log_has_only_error_type(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        events: list[tuple] = []

        class _Log:
            def debug(self, event, **kw):
                events.append((event, kw))

            def warning(self, event, **kw):
                events.append((event, kw))

        monkeypatch.setattr(rx, "log", _Log())
        bot = _FakeBot(raise_exc=RuntimeError("secret-ish text should not be logged"))
        await rx.maybe_react_processing(bot, _msg())
        failed = [e for e in events if e[0] == "telegram_reaction_failed"]
        assert failed
        for _e, kw in failed:
            assert "error_type" in kw
            assert "secret-ish" not in str(kw)


# ── Structured event names ───────────────────────────────────────────────────


class TestStructuredEvents:
    async def test_set_event_emitted(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        events = []
        monkeypatch.setattr(
            rx,
            "log",
            SimpleNamespace(
                debug=lambda e, **k: events.append(e), warning=lambda e, **k: events.append(e)
            ),
        )
        await rx.maybe_react_processing(_FakeBot(), _msg())
        assert "telegram_reaction_set" in events

    async def test_clear_event_emitted(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        events = []
        monkeypatch.setattr(
            rx,
            "log",
            SimpleNamespace(
                debug=lambda e, **k: events.append(e), warning=lambda e, **k: events.append(e)
            ),
        )
        await rx.maybe_clear_reaction(_FakeBot(), _msg())
        assert "telegram_reaction_clear" in events

    async def test_failed_event_emitted(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        events = []
        monkeypatch.setattr(
            rx,
            "log",
            SimpleNamespace(
                debug=lambda e, **k: events.append(e), warning=lambda e, **k: events.append(e)
            ),
        )
        await rx.maybe_react_processing(_FakeBot(raise_exc=RuntimeError("x")), _msg())
        assert "telegram_reaction_failed" in events


# ── Default-OFF contract (real settings) ─────────────────────────────────────


class TestDefaultOffContract:
    def test_setting_default_false(self):
        from shared.config.settings import TelegramSettings

        assert TelegramSettings().reactions_enabled is False

    def test_groups_default_false(self):
        from shared.config.settings import TelegramSettings

        assert TelegramSettings().reactions_groups_enabled is False

    def test_clear_on_reply_default_true(self):
        from shared.config.settings import TelegramSettings

        assert TelegramSettings().reaction_clear_on_reply is True

    def test_default_processing_emoji(self):
        from shared.config.settings import TelegramSettings

        assert TelegramSettings().reaction_processing == "👀"

    def test_settings_exposed_on_root(self):
        from shared.config import get_settings

        assert hasattr(get_settings(), "telegram")

    async def test_real_settings_default_no_call(self):
        # No monkeypatch: uses real settings (default OFF) → must be a no-op.
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls == []


# ── Source-pin: handlers wire the helper around the OpenAI path ──────────────


class TestHandlerWiring:
    def _src(self) -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_imports_helper(self):
        s = self._src()
        assert "from apps.bot.utils.reactions import" in s
        assert "maybe_react_processing" in s
        assert "maybe_react_done" in s
        assert "maybe_clear_reaction" in s

    def test_two_processing_calls(self):
        assert self._src().count("maybe_react_processing(message.bot, message)") == 2

    def test_two_done_calls(self):
        assert self._src().count("maybe_react_done(message.bot, message)") == 2

    def test_two_clear_calls(self):
        assert self._src().count("maybe_clear_reaction(message.bot, message)") == 2

    def test_processing_before_call_ai(self):
        s = self._src()
        # In each handler the processing reaction precedes the _call_ai try block.
        assert s.index("maybe_react_processing") < s.index("result = await _call_ai")

    def test_clear_in_failure_path(self):
        s = self._src()
        # clear appears alongside the openai_error capture in the except block
        assert (
            "_schedule_unknown_capture(" in s and "maybe_clear_reaction(message.bot, message)" in s
        )

    def test_no_extra_typing_text_added(self):
        # We must not add extra customer-facing "typing..." text messages.
        s = self._src()
        assert "typing..." not in s.lower()
        assert "yozyapti" not in s.lower()


class TestUnchangedBehaviorPins:
    def _src(self) -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_stop_safety_guard_intact(self):
        assert "_maybe_block_stop_or_safety(message, state, user_id, text)" in self._src()

    def test_failsafe_reply_intact(self):
        assert "await message.answer(_FAILSAFE_TEXT" in self._src()

    def test_unknown_capture_intact(self):
        assert self._src().count('reason="openai_error"') >= 2

    def test_safety_block_capture_intact(self):
        assert 'reason="safety_block"' in self._src()

    def test_reply_text_send_intact(self):
        s = self._src()
        assert "await message.answer(reply_text, reply_markup=_ai_keyboard())" in s
        assert "await message.answer(reply_text)" in s


# ── Parametrized emoji / gating coverage ─────────────────────────────────────


class TestEmojiVariants:
    @pytest.mark.parametrize("emoji", ["👀", "👍", "🔥", "❤️", "🎉"])
    async def test_processing_various_configured(self, monkeypatch, emoji):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, processing=emoji))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls[0]["emojis"] == [emoji]

    @pytest.mark.parametrize("emoji", ["✅", "👍", "🔥"])
    async def test_done_various_configured(self, monkeypatch, emoji):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False, done=emoji))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert bot.calls[0]["emojis"] == [emoji]

    @pytest.mark.parametrize(
        "ctype,allowed",
        [("private", True), ("group", False), ("supergroup", False), ("channel", False)],
    )
    async def test_gating_matrix_default(self, monkeypatch, ctype, allowed):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, groups=False))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg(chat_type=ctype))
        assert (len(bot.calls) == 1) is allowed


class TestProcessingEmptyConfigFallback:
    async def test_empty_processing_falls_back_to_eyes(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, processing=""))
        bot = _FakeBot()
        await rx.maybe_react_processing(bot, _msg())
        assert bot.calls[0]["emojis"] == ["👀"]

    async def test_empty_done_falls_back_to_check(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False, done=""))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert bot.calls[0]["emojis"] == ["✅"]


class TestRetryAfterSafety:
    async def test_retry_after_swallowed(self, monkeypatch):
        from aiogram.exceptions import TelegramRetryAfter

        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        try:
            exc = TelegramRetryAfter(method=SimpleNamespace(), message="flood", retry_after=5)
        except Exception:
            exc = RuntimeError("flood")
        bot = _FakeBot(raise_exc=exc)
        await rx.maybe_react_processing(bot, _msg())  # must not raise


class TestIdempotentNoState:
    async def test_helper_holds_no_module_state(self, monkeypatch):
        # Calling repeatedly must not accumulate any state in the module.
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        for _ in range(3):
            await rx.maybe_react_processing(bot, _msg())
        assert len(bot.calls) == 3


# ── try/finally hardening (source-pin) ───────────────────────────────────────


class TestFinallyHardening:
    """Pin the guard that guarantees the processing reaction is always resolved.

    Handler-level execution is heavy (deep monkeypatching), so per the test
    convention we source-pin the structure and unit-test the helper semantics.
    """

    def _src(self) -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_each_handler_has_finally_guard(self):
        # Two handlers → two finally-based resolve guards.
        assert self._src().count("if not _reaction_resolved:") == 2

    def test_resolved_flag_initialized_false(self):
        assert self._src().count("_reaction_resolved = False") == 2

    def test_resolved_flag_set_true_on_success(self):
        assert self._src().count("_reaction_resolved = True") == 2

    def test_finally_keyword_present_after_processing(self):
        s = self._src()
        # The processing call precedes a finally block in each handler.
        assert s.count("maybe_react_processing(message.bot, message)") == 2
        assert "finally:" in s

    def test_clear_lives_in_finally_not_only_except(self):
        # The clear is reached via the finally guard (paired with the resolved flag).
        s = self._src()
        i_flag = s.index("if not _reaction_resolved:")
        i_clear = s.index("maybe_clear_reaction(message.bot, message)")
        assert i_clear > i_flag

    def test_done_sets_resolved_before_finally(self):
        s = self._src()
        i_done = s.index("maybe_react_done(message.bot, message)")
        i_true = s.index("_reaction_resolved = True")
        assert i_true > i_done  # resolved flag set right after done

    def test_processing_still_before_call_ai(self):
        s = self._src()
        assert s.index("maybe_react_processing") < s.index("result = await _call_ai")

    def test_no_duplicate_explicit_clear_in_except(self):
        # The old explicit clear inside the except block is gone; resolution is
        # centralized in finally. So there are exactly 2 clear calls total
        # (one finally per handler), not 4.
        assert self._src().count("maybe_clear_reaction(message.bot, message)") == 2

    def test_return_comment_documents_finally(self):
        assert self._src().count("finally below clears the reaction") == 2


class TestResolveSemantics:
    """Unit-test the resolve semantics the finally guard relies on."""

    async def test_success_resolves_once(self, monkeypatch):
        # done() in clear mode → exactly one API call (the clear), resolved=True
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=True))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        assert len(bot.calls) == 1 and bot.calls[0]["cleared"] is True

    async def test_except_path_clear_resolves(self, monkeypatch):
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_clear_reaction(bot, _msg())
        assert bot.calls and bot.calls[0]["cleared"] is True

    async def test_double_clear_no_bad_side_effect(self, monkeypatch):
        # finally may clear after an except already cleared elsewhere — a double
        # clear must be harmless (both empty-list, no raise).
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot()
        await rx.maybe_clear_reaction(bot, _msg())
        await rx.maybe_clear_reaction(bot, _msg())
        assert len(bot.calls) == 2
        assert all(c["cleared"] for c in bot.calls)

    async def test_clear_in_finally_failure_swallowed(self, monkeypatch):
        # If the finally clear hits a Telegram error it must not propagate.
        _patch_cfg(monkeypatch, _Cfg(enabled=True))
        bot = _FakeBot(raise_exc=RuntimeError("finally boom"))
        await rx.maybe_clear_reaction(bot, _msg())  # must not raise

    async def test_done_then_clear_is_safe(self, monkeypatch):
        # done (resolved) followed by a defensive clear → both safe.
        _patch_cfg(monkeypatch, _Cfg(enabled=True, clear_on_reply=False, done="✅"))
        bot = _FakeBot()
        await rx.maybe_react_done(bot, _msg())
        await rx.maybe_clear_reaction(bot, _msg())
        assert bot.calls[0]["emojis"] == ["✅"]
        assert bot.calls[1]["cleared"] is True

    async def test_flag_off_finally_clear_noop(self, monkeypatch):
        # When the feature is off, even the finally-path clear does nothing.
        _patch_cfg(monkeypatch, _Cfg(enabled=False))
        bot = _FakeBot()
        await rx.maybe_clear_reaction(bot, _msg())
        assert bot.calls == []


class TestUnchangedBehaviorAfterHardening:
    def _src(self) -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_stop_safety_guard_intact(self):
        assert "_maybe_block_stop_or_safety(message, state, user_id, text)" in self._src()

    def test_failsafe_reply_intact(self):
        assert "await message.answer(_FAILSAFE_TEXT" in self._src()

    def test_success_reply_intact(self):
        s = self._src()
        assert "await message.answer(reply_text, reply_markup=_ai_keyboard())" in s
        assert "await message.answer(reply_text)" in s

    def test_unknown_capture_openai_intact(self):
        assert self._src().count('reason="openai_error"') == 2

    def test_unknown_capture_safety_intact(self):
        assert 'reason="safety_block"' in self._src()

    def test_capture_before_return_in_except(self):
        # Within the except, capture is scheduled before the return (ordering
        # unchanged); the finally then clears.
        s = self._src()
        i_cap = s.index("_schedule_unknown_capture(")
        i_ret = s.index("return  # finally below clears the reaction")
        assert i_cap < i_ret

    def test_no_typing_text_added(self):
        s = self._src().lower()
        assert "typing..." not in s and "yozyapti" not in s


# ── Helper import smoke ──────────────────────────────────────────────────────


class TestImportSmoke:
    def test_helper_module_imports(self):
        import apps.bot.utils.reactions as m

        assert callable(m.maybe_react_processing)
        assert callable(m.maybe_react_done)
        assert callable(m.maybe_clear_reaction)

    def test_ai_support_imports(self):
        import apps.bot.handlers.private.ai_support as m

        assert m.router is not None
