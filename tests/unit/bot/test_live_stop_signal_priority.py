"""Phase 2 — live stop-signal / low-interest priority fix.

Shadow test found that "kerakmas" in the waiting_for_ai_question state was
routed to the angry-objection branch (which asks for a phone) instead of a
polite stop. These tests pin the new detectors and the shared early guard so
stop / low-interest wins BEFORE objection/price, without breaking objection,
operator, price, or catalog routing.

Pure / offline: no network, Redis, DB, OpenAI, Telegram.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import apps.bot.handlers.private.ai_support as ai_support
from apps.bot.handlers.private.ai_detection import (
    _is_hard_stop,
    _is_low_interest_stop,
    _is_safety_block,
)


class _Msg:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=111)
        self.chat = SimpleNamespace(id=222, type="private")
        self.answers: list[str] = []

    async def answer(self, text: str, **kw: object) -> None:
        self.answers.append(text)


class _State:
    def __init__(self, data: dict | None = None) -> None:
        self._d = data or {}
        self.mutated = False

    async def get_data(self) -> dict:
        return dict(self._d)

    async def update_data(self, **kw: object) -> None:  # pragma: no cover - guard not expected
        self.mutated = True

    async def set_state(self, *_a: object) -> None:  # pragma: no cover
        self.mutated = True

    async def clear(self) -> None:  # pragma: no cover
        self.mutated = True


@pytest.fixture(autouse=True)
def _no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(_uid: int) -> None:
        return None

    monkeypatch.setattr(ai_support, "_disable_followups_on_stop", _noop)


async def _guard(text: str, data: dict | None = None) -> tuple[bool, _Msg, _State]:
    msg, state = _Msg(text), _State(data)
    handled = await ai_support._maybe_block_stop_or_safety(msg, state, 111, text)
    return handled, msg, state


# ── Detector: hard stop ───────────────────────────────────────────────────

_HARD_STOPS = ["kerakmas", "kerak emas", "kerak emas.", "kerakmas!", "hozir kerakmas", "stop"]
_SOFT_LOW_INTEREST = ["keyinroq", "shunchaki soradim", "shunchaki so'radim", "hozircha kerakmas"]
_NOT_STOP = [
    "qimmatku",
    "juda qimmat",
    "operator kerak",
    "gulli nechi",
    "20kv guli",
    "gulli katalog",
    "kafolat bormi",
    "salom",
]


class TestStopDetectors:
    @pytest.mark.parametrize("text", _HARD_STOPS)
    def test_hard_stop_detected(self, text: str) -> None:
        assert _is_hard_stop(text) is True
        assert _is_low_interest_stop(text) is True

    @pytest.mark.parametrize("text", _SOFT_LOW_INTEREST)
    def test_soft_low_interest_detected(self, text: str) -> None:
        assert _is_low_interest_stop(text) is True

    def test_keyinroq_is_soft_not_hard(self) -> None:
        # "keyinroq" is a soft postpone, not a hard opt-out.
        assert _is_low_interest_stop("keyinroq") is True
        assert _is_hard_stop("keyinroq") is False

    @pytest.mark.parametrize("text", _NOT_STOP)
    def test_keep_phrases_not_stop(self, text: str) -> None:
        assert _is_low_interest_stop(text) is False
        assert _is_hard_stop(text) is False

    def test_operator_kerak_not_stop(self) -> None:
        # "operator kerak" ends with "kerak" (no emas/mas) — must NOT be stop.
        assert _is_low_interest_stop("operator kerak") is False

    def test_cyrillic_stop(self) -> None:
        assert _is_low_interest_stop("керакмас") is True


# ── Guard behaviour ───────────────────────────────────────────────────────


class TestGuardStop:
    @pytest.mark.parametrize("text", _HARD_STOPS)
    async def test_hard_stop_handled_with_polite_reply(self, text: str) -> None:
        handled, msg, state = await _guard(text)
        assert handled is True
        assert len(msg.answers) == 1
        assert "yubormaymiz" in msg.answers[0].lower()
        # must NOT ask for phone / objection
        assert "telefon" not in msg.answers[0].lower()
        assert state.mutated is False

    @pytest.mark.parametrize("text", _SOFT_LOW_INTEREST)
    async def test_soft_low_interest_polite_no_phone(self, text: str) -> None:
        handled, msg, _ = await _guard(text)
        assert handled is True
        reply = msg.answers[0].lower()
        # A polite stop / low-interest reply (either wording), never a phone ask.
        assert "tushunarli" in reply
        assert "telefon" not in reply
        assert "raqam" not in reply

    async def test_keyinroq_uses_soft_wording(self) -> None:
        _, msg, _ = await _guard("keyinroq")
        assert "shoshilmang" in msg.answers[0].lower()

    @pytest.mark.parametrize("text", _NOT_STOP)
    async def test_keep_phrases_not_handled_by_guard(self, text: str) -> None:
        # Safety phrases would be handled; these are neither stop nor safety.
        handled, msg, _ = await _guard(text)
        if _is_safety_block(text):
            pytest.skip("safety phrase")
        assert handled is False
        assert msg.answers == []

    async def test_hard_stop_disables_followups(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: list[int] = []

        async def _rec(uid: int) -> None:
            called.append(uid)

        monkeypatch.setattr(ai_support, "_disable_followups_on_stop", _rec)
        await _guard("kerak emas")
        assert called == [111]

    async def test_soft_does_not_disable_followups(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: list[int] = []

        async def _rec(uid: int) -> None:
            called.append(uid)

        monkeypatch.setattr(ai_support, "_disable_followups_on_stop", _rec)
        await _guard("keyinroq")
        assert called == []  # soft low-interest must not hard-disable follow-ups

    async def test_objection_phrase_falls_through(self) -> None:
        handled, msg, _ = await _guard("qimmatku")
        assert handled is False  # objection handled later, not by the guard

    async def test_price_phrase_falls_through(self) -> None:
        handled, _, _ = await _guard("gulli nechi")
        assert handled is False

    async def test_catalog_phrase_falls_through(self) -> None:
        handled, _, _ = await _guard("gulli katalog")
        assert handled is False

    async def test_operator_phrase_falls_through(self) -> None:
        handled, _, _ = await _guard("operator kerak")
        assert handled is False


class TestGuardWiredInHandlers:
    def test_both_handlers_call_guard(self) -> None:
        import inspect

        src = inspect.getsource(ai_support)
        assert src.count("_maybe_block_stop_or_safety(message, state, user_id, text)") == 2

    def test_old_redundant_stop_block_removed(self) -> None:
        import inspect

        src = inspect.getsource(ai_support)
        # The old inline FuSvc.is_stop_signal block was removed in favour of the guard.
        assert "if _FuSvc.is_stop_signal(text):" not in src
