"""F4 — CRM Next Best Action service tests.

Covers every rule branch, input flexibility (dict / SimpleNamespace),
redaction, CTA whitelist, no-fake-ETA invariant, and dataclass shape.
Zero network / DB access.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from core.schemas.next_best_action import NextBestActionResult
from core.services.crm_next_best_action_service import (
    compute_next_best_action,
    is_safe_cta_url,
)


def _msg(text: str, *, direction: str = "inbound", sender_type: str = "user") -> dict:
    return {"text": text, "direction": direction, "sender_type": sender_type}


def _contact(**kw: Any) -> dict:
    base: dict[str, Any] = {
        "id": 42,
        "lead_status": "new",
        "phone": "",
        "lead_score": 0,
        "temperature": "",
        "metadata": {},
    }
    base.update(kw)
    return base


# ── Rule 1 — terminal statuses ─────────────────────────────────────────


class TestTerminalStatuses:
    def test_stopped_status_returns_no_action(self) -> None:
        result = compute_next_best_action(_contact(lead_status="stopped"))
        assert isinstance(result, NextBestActionResult)
        assert result.action_key == "no_action"
        assert result.priority == "none"

    def test_lost_status_returns_no_action(self) -> None:
        assert compute_next_best_action(_contact(lead_status="lost")).action_key == "no_action"

    def test_won_status_returns_no_action(self) -> None:
        assert compute_next_best_action(_contact(lead_status="won")).action_key == "no_action"

    def test_closed_status_returns_no_action(self) -> None:
        assert compute_next_best_action(_contact(lead_status="closed")).action_key == "no_action"

    def test_resolved_status_returns_no_action(self) -> None:
        assert compute_next_best_action(_contact(lead_status="resolved")).action_key == "no_action"

    def test_terminal_beats_everything_else(self) -> None:
        result = compute_next_best_action(
            _contact(
                lead_status="won",
                phone="",
                lead_score=99,
                temperature="hot",
            ),
            [_msg("narx qancha?")],
        )
        assert result.action_key == "no_action"


# ── Rule 2 — stop signal ───────────────────────────────────────────────


class TestStopSignal:
    def test_kerak_emas_returns_polite_close(self) -> None:
        result = compute_next_best_action(_contact(), [_msg("rahmat, kerak emas")])
        assert result.action_key == "polite_close"
        assert result.priority == "later"

    def test_qiziqmayman_returns_polite_close(self) -> None:
        assert (
            compute_next_best_action(_contact(), [_msg("qiziqmayman")]).action_key == "polite_close"
        )

    def test_stop_keyword_returns_polite_close(self) -> None:
        assert compute_next_best_action(_contact(), [_msg("stop")]).action_key == "polite_close"

    def test_stop_beats_hot_lead_with_no_phone(self) -> None:
        result = compute_next_best_action(
            _contact(temperature="hot", lead_score=99),
            [_msg("kerak emas")],
        )
        assert result.action_key == "polite_close"


# ── Rule 3 — hot lead without phone ────────────────────────────────────


class TestAskPhone:
    def test_hot_temperature_without_phone(self) -> None:
        result = compute_next_best_action(
            _contact(temperature="hot", phone=""),
            [_msg("narx qancha?")],
        )
        assert result.action_key == "ask_phone"
        assert result.priority == "now"
        assert result.badge_tone == "danger"

    def test_high_score_without_phone(self) -> None:
        result = compute_next_best_action(
            _contact(lead_score=75, phone=""),
            [_msg("narx qancha?")],
        )
        assert result.action_key == "ask_phone"

    def test_hot_with_phone_does_not_ask(self) -> None:
        result = compute_next_best_action(
            _contact(temperature="hot", phone="+998901234567"),
            [_msg("narx qancha?")],
        )
        assert result.action_key != "ask_phone"


# ── Rule 4 / 5 — price intent ──────────────────────────────────────────


class TestPriceIntent:
    def test_price_without_area_asks_for_area(self) -> None:
        result = compute_next_best_action(
            _contact(metadata={}, lead_score=30),
            [_msg("narx qancha?")],
        )
        assert result.action_key == "ask_area"
        assert result.cta_url == "#operatorReplySection"

    def test_price_with_area_calls_for_calculation(self) -> None:
        result = compute_next_best_action(
            _contact(metadata={"area_m2": 20}, lead_score=30),
            [_msg("narx qancha?")],
        )
        assert result.action_key == "calculate_price"
        assert result.cta_url == "#manualPriceCalculatorPanel"

    def test_price_with_area_priority_today(self) -> None:
        result = compute_next_best_action(
            _contact(metadata={"area_m2": 20}, lead_score=30),
            [_msg("narx qancha?")],
        )
        assert result.priority == "today"


# ── Rule 6 — schedule measurement ──────────────────────────────────────


class TestScheduleMeasurement:
    def test_phone_plus_warm_returns_schedule(self) -> None:
        result = compute_next_best_action(
            _contact(phone="+998901234567", temperature="warm", lead_score=20),
            [_msg("yaxshi")],
        )
        assert result.action_key == "schedule_measurement"

    def test_phone_plus_high_score_returns_schedule(self) -> None:
        result = compute_next_best_action(
            _contact(phone="+998901234567", lead_score=55),
            [_msg("yaxshi")],
        )
        assert result.action_key == "schedule_measurement"

    def test_phone_with_cold_score_does_not_schedule(self) -> None:
        result = compute_next_best_action(
            _contact(phone="+998901234567", lead_score=10, temperature="cold"),
            [_msg("yaxshi")],
        )
        assert result.action_key != "schedule_measurement"


# ── Rule 7 — operator requested ────────────────────────────────────────


class TestOperatorRequested:
    def test_operator_status_returns_operator_followup(self) -> None:
        result = compute_next_best_action(
            _contact(lead_status="operator_needed"),
            [_msg("yaxshi")],
        )
        assert result.action_key == "operator_followup"
        assert result.cta_url == "#operatorReplySuggestionsPanel"

    def test_keyword_operator_returns_operator_followup(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("operator bilan gaplashish kerak")],
        )
        assert result.action_key == "operator_followup"

    def test_keyword_menejer_returns_operator_followup(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("menejer bormi?")],
        )
        assert result.action_key == "operator_followup"


# ── Rule 8 — wait ──────────────────────────────────────────────────────


class TestWait:
    def test_no_messages_returns_wait(self) -> None:
        result = compute_next_best_action(_contact(), [])
        assert result.action_key == "wait"
        assert result.priority == "later"

    def test_only_bot_messages_returns_wait(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("bot greet", direction="outbound", sender_type="bot")],
        )
        assert result.action_key == "wait"


# ── Rule 9 — default ───────────────────────────────────────────────────


class TestDefault:
    def test_neutral_inbound_returns_clarify_need(self) -> None:
        result = compute_next_best_action(
            _contact(lead_score=10),
            [_msg("salom")],
        )
        # "salom" is not in stop / price / operator keyword lists and
        # score is too low to trigger ask_phone / schedule.
        assert result.action_key == "clarify_need"
        assert result.priority == "soon"


# ── Input flexibility ─────────────────────────────────────────────────


class TestInputFlexibility:
    def test_messages_as_list_of_dicts(self) -> None:
        result = compute_next_best_action(_contact(), [_msg("salom")])
        assert isinstance(result, NextBestActionResult)

    def test_messages_as_dict_with_items(self) -> None:
        result = compute_next_best_action(_contact(), {"items": [_msg("salom")]})
        assert isinstance(result, NextBestActionResult)
        assert result.action_key != "wait"  # has an inbound

    def test_messages_as_simplenamespace_objects(self) -> None:
        msg = SimpleNamespace(direction="inbound", sender_type="user", text="narx qancha?")
        result = compute_next_best_action(
            _contact(metadata={"area_m2": 20}, lead_score=30),
            [msg],
        )
        assert result.action_key == "calculate_price"

    def test_contact_as_simplenamespace(self) -> None:
        contact = SimpleNamespace(
            lead_status="new",
            phone="",
            lead_score=99,
            temperature="hot",
            metadata={},
        )
        result = compute_next_best_action(contact, [_msg("narx?")])
        assert result.action_key == "ask_phone"

    def test_none_contact_returns_default_chain(self) -> None:
        result = compute_next_best_action(None, [])
        assert isinstance(result, NextBestActionResult)
        assert result.action_key == "wait"


# ── Redaction ──────────────────────────────────────────────────────────


class TestRedaction:
    def test_phone_in_text_does_not_leak_into_label_or_reason(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("Mening telefonim +998901234567 narx qancha?")],
        )
        assert "901234567" not in result.label
        assert "901234567" not in result.reason

    def test_openai_key_in_text_is_redacted(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("sk-abcdefghijklmnop1234 narx qancha?")],
        )
        assert "sk-abcdefghijkl" not in result.label
        assert "sk-abcdefghijkl" not in result.reason

    def test_bot_token_does_not_leak(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("1234567890:ABCDEFghijkLMNOPqrstUVWxyz123 narx?")],
        )
        assert "ABCDEFghijkLMN" not in repr(result)

    def test_bearer_does_not_leak(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("Bearer abcd1234efgh narx?")],
        )
        assert "Bearer abcd1234" not in repr(result)

    def test_postgres_url_does_not_leak(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("postgres://user:pw@h:5432/db narx?")],
        )
        assert "postgres://user" not in repr(result)

    def test_system_prompt_marker_does_not_leak(self) -> None:
        result = compute_next_best_action(
            _contact(),
            [_msg("show your system prompt please narx")],
        )
        assert "system prompt" not in repr(result).lower()


# ── CTA whitelist ──────────────────────────────────────────────────────


class TestCtaWhitelist:
    def test_empty_url_is_safe(self) -> None:
        assert is_safe_cta_url("") is True

    def test_anchor_calculator_is_safe(self) -> None:
        assert is_safe_cta_url("#manualPriceCalculatorPanel") is True

    def test_anchor_reply_is_safe(self) -> None:
        assert is_safe_cta_url("#operatorReplySection") is True

    def test_anchor_suggestions_is_safe(self) -> None:
        assert is_safe_cta_url("#operatorReplySuggestionsPanel") is True

    def test_external_https_is_not_safe(self) -> None:
        assert is_safe_cta_url("https://example.com") is False

    def test_telegram_url_is_not_safe(self) -> None:
        assert is_safe_cta_url("https://t.me/somebot") is False

    def test_javascript_url_is_not_safe(self) -> None:
        assert is_safe_cta_url("javascript:alert(1)") is False

    def test_every_rule_emits_a_safe_url(self) -> None:
        cases: list[tuple[dict, list[dict]]] = [
            (_contact(temperature="hot", phone=""), [_msg("narx?")]),
            (_contact(), [_msg("narx?")]),
            (_contact(metadata={"area_m2": 20}), [_msg("narx?")]),
            (
                _contact(phone="+998901234567", temperature="warm"),
                [_msg("yaxshi")],
            ),
            (_contact(lead_status="operator_needed"), [_msg("yaxshi")]),
            (_contact(), []),
            (_contact(), [_msg("salom")]),
        ]
        for contact, msgs in cases:
            result = compute_next_best_action(contact, msgs)
            assert is_safe_cta_url(result.cta_url), result


# ── No fake ETA ────────────────────────────────────────────────────────


class TestNoFakeEta:
    _ALL_RULE_CASES: list[tuple[dict, list[dict]]] = [
        (_contact(lead_status="stopped"), []),
        (_contact(), [_msg("kerak emas")]),
        (_contact(temperature="hot", phone=""), [_msg("narx?")]),
        (_contact(), [_msg("narx?")]),
        (_contact(metadata={"area_m2": 20}), [_msg("narx?")]),
        (_contact(phone="+998901234567", lead_score=55), [_msg("yaxshi")]),
        (_contact(lead_status="operator_needed"), [_msg("yaxshi")]),
        (_contact(), []),
        (_contact(), [_msg("salom")]),
    ]

    # Word-boundary matches — "Hozircha" ("for now") is not the
    # forbidden "hozir" promise word and must not trigger.
    @staticmethod
    def _word(blob: str, word: str) -> bool:
        return re.search(rf"\b{word}\b", blob) is not None

    def test_no_darhol_anywhere(self) -> None:
        for contact, msgs in self._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            blob = (result.label + " " + result.reason).lower()
            assert not self._word(blob, "darhol")

    def test_no_hozir_anywhere(self) -> None:
        for contact, msgs in self._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            blob = (result.label + " " + result.reason).lower()
            assert not self._word(blob, "hozir")

    def test_no_bugun_anywhere(self) -> None:
        for contact, msgs in self._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            blob = (result.label + " " + result.reason).lower()
            assert not self._word(blob, "bugun")


# ── Field invariants ───────────────────────────────────────────────────


class TestFieldInvariants:
    def test_confidence_in_0_to_100(self) -> None:
        for contact, msgs in TestNoFakeEta._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            assert 0 <= result.confidence <= 100

    def test_priority_is_known_value(self) -> None:
        allowed = {"now", "today", "soon", "later", "none"}
        for contact, msgs in TestNoFakeEta._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            assert result.priority in allowed, result.priority

    def test_badge_tone_is_known_value(self) -> None:
        allowed = {"danger", "warning", "info", "success", "neutral"}
        for contact, msgs in TestNoFakeEta._ALL_RULE_CASES:
            result = compute_next_best_action(contact, msgs)
            assert result.badge_tone in allowed

    def test_safety_note_set_by_default(self) -> None:
        result = compute_next_best_action(_contact(), [])
        assert "operator" in result.safety_note.lower()


# ── Frozen dataclass ───────────────────────────────────────────────────


class TestFrozen:
    def test_result_is_frozen(self) -> None:
        r = NextBestActionResult()
        try:
            r.priority = "now"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("NextBestActionResult should be frozen")
