"""Phase 5 — shadow coverage for catalog + measurement entry points.

Shadow test found that "gulli katalog" and "kelib korila" bypassed the shadow
hook because they were handled by the catalog / measurement handlers, which sit
outside the two generic AI text handlers. This extends the shadow hook (still
default OFF) to those entry points via fire_shadow_for_message.

Pure / offline: no network, Redis, DB, OpenAI, Telegram.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import apps.bot.handlers.private.sales_dialogue_shadow as shadow
from apps.bot.handlers.private.sales_dialogue_shadow import fire_shadow_for_message


class _Msg:
    def __init__(self, text: str = "gulli katalog") -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=42)
        self.chat = SimpleNamespace(id=-100999, type="private")
        self.answers: list[str] = []
        self.bot = None

    async def answer(self, text: str, **kw: object) -> None:
        self.answers.append(text)


class _State:
    def __init__(self, data: dict | None = None) -> None:
        self._d = data or {}
        self.get_calls = 0
        self.mutations = 0

    async def get_data(self) -> dict:
        self.get_calls += 1
        return dict(self._d)

    async def update_data(self, **kw: object) -> None:
        self.mutations += 1

    async def set_state(self, *_a: object) -> None:
        self.mutations += 1

    async def clear(self) -> None:
        self.mutations += 1


def _set_flag(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    ns = SimpleNamespace(business=SimpleNamespace(sales_dialogue_manager_shadow_enabled=value))
    monkeypatch.setattr(shadow, "get_settings", lambda: ns)


def _capture_helper(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    async def _rec(**kw: object) -> None:
        calls.append(dict(kw))

    monkeypatch.setattr(shadow, "maybe_log_sales_dialogue_shadow", _rec)
    return calls


# ── fire_shadow_for_message ────────────────────────────────────────────────


class TestFireShadow:
    async def test_flag_off_no_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, False)
        calls = _capture_helper(monkeypatch)
        st = _State({"price_design": "gulli"})
        await fire_shadow_for_message(_Msg(), st, live_route="catalog")
        assert calls == []
        assert st.get_calls == 0  # flag off → never reads FSM state

    async def test_flag_on_calls_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        await fire_shadow_for_message(_Msg("gulli katalog"), _State(), live_route="catalog")
        assert len(calls) == 1
        assert calls[0]["live_route"] == "catalog"
        assert calls[0]["text"] == "gulli katalog"
        assert calls[0]["user_id"] == 42

    async def test_measurement_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        await fire_shadow_for_message(_Msg("kelib korila"), _State(), live_route="measurement")
        assert calls[0]["live_route"] == "measurement"

    async def test_passes_state_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        st = _State({"price_design": "gulli", "price_area": 20})
        await fire_shadow_for_message(_Msg(), st, live_route="catalog")
        assert calls[0]["state_data"] == {"price_design": "gulli", "price_area": 20}
        assert st.get_calls == 1

    async def test_no_message_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        _capture_helper(monkeypatch)
        msg = _Msg()
        await fire_shadow_for_message(msg, _State(), live_route="catalog")
        assert msg.answers == []  # shadow never replies

    async def test_no_state_mutation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        _capture_helper(monkeypatch)
        st = _State()
        await fire_shadow_for_message(_Msg(), st, live_route="catalog")
        assert st.mutations == 0  # only get_data (read), never set/clear/update

    async def test_exception_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)

        async def _boom(**kw: object) -> None:
            raise RuntimeError("nope")

        monkeypatch.setattr(shadow, "maybe_log_sales_dialogue_shadow", _boom)
        # must not raise
        await fire_shadow_for_message(_Msg(), _State(), live_route="catalog")

    async def test_none_state_safe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        await fire_shadow_for_message(_Msg(), None, live_route="catalog")
        assert len(calls) == 1
        assert calls[0]["state_data"] is None

    async def test_empty_text_still_forwards(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # empty-text gating is the helper's job; fire wrapper just forwards.
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        await fire_shadow_for_message(_Msg(""), _State(), live_route="catalog")
        assert calls[0]["text"] == ""

    async def test_missing_from_user_safe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_flag(monkeypatch, True)
        calls = _capture_helper(monkeypatch)
        msg = _Msg()
        msg.from_user = None
        await fire_shadow_for_message(msg, _State(), live_route="catalog")
        assert calls[0]["user_id"] is None


# ── Entry points call the shadow wrapper ───────────────────────────────────


class TestEntryPointsWired:
    async def test_catalog_button_fires_shadow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.bot.handlers.private.ai_support as ai_support

        recorded: list[str] = []

        async def _rec(message: object, state: object, *, live_route: str) -> None:
            recorded.append(live_route)

        monkeypatch.setattr(shadow, "fire_shadow_for_message", _rec)
        await ai_support.handle_ai_catalog_btn(_Msg("📂 Katalog"), _State())
        assert recorded == ["catalog"]

    async def test_measurement_flow_fires_shadow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import apps.bot.handlers.private.measurement_lead as ml

        recorded: list[str] = []

        async def _rec(message: object, state: object, *, live_route: str) -> None:
            recorded.append(live_route)

        monkeypatch.setattr(shadow, "fire_shadow_for_message", _rec)
        await ml.start_measurement_flow(_Msg("kelib korila"), _State())
        assert recorded == ["measurement"]

    async def test_measurement_flow_shadow_before_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The shadow call must run before state.clear() so FSM facts survive.
        import apps.bot.handlers.private.measurement_lead as ml

        order: list[str] = []

        async def _rec(message: object, state: object, *, live_route: str) -> None:
            order.append("shadow")

        st = _State()
        orig_clear = st.clear

        async def _clear() -> None:
            order.append("clear")
            await orig_clear()

        st.clear = _clear  # type: ignore[method-assign]
        monkeypatch.setattr(shadow, "fire_shadow_for_message", _rec)
        await ml.start_measurement_flow(_Msg(), st)
        assert order == ["shadow", "clear"]


# ── Default OFF guarantee ──────────────────────────────────────────────────


class TestDefaultOff:
    def test_shadow_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings

        assert (
            BusinessSettings.model_fields["sales_dialogue_manager_shadow_enabled"].default is False
        )
