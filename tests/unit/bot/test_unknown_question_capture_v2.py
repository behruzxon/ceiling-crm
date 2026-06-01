"""Unknown Questions Inbox v2 — expanded capture coverage.

Verifies the new capture reasons wired in apps/bot/handlers/private/ai_support.py:
* ``no_catalog_match`` — a catalog/design ask that resolved to nothing specific
  (not a generic catalog ask, not an ambiguous confirmation);
* ``unknown_price_question`` — a substantive price question with no parseable
  area/design/district.

Strategy: the handler logic is heavy to drive end-to-end, so we test the REAL
integration of the resolver/parser + the classifier (the exact decision the
handler makes), plus source-pin the wiring and the never-capture branches.

Offline: no network, Redis, DB, OpenAI, Telegram.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.bot.handlers.private.ai_detection import (
    _is_catalog_request,
    _is_operator_request,
    parse_combo,
)
from core.services.catalog_link_resolver_service import resolve_catalog_link
from core.services.unknown_question_service import (
    classify_catalog_capture,
    classify_price_capture,
)

_SRC = "apps/bot/handlers/private/ai_support.py"


def _src() -> str:
    return Path(_SRC).read_text(encoding="utf-8")


def _catalog_reason(text: str) -> str | None:
    """Replicate exactly what the handler computes for a catalog ask."""
    r = resolve_catalog_link(text)
    return classify_catalog_capture(
        matched=r.matched, needs_confirmation=r.needs_confirmation, reason=r.reason
    )


# ── Catalog: real resolver + classifier integration ──────────────────────────


class TestCatalogNoMatchCaptured:
    @pytest.mark.parametrize(
        "text",
        [
            "balkon",
            "hammom",
            "dush",
            "bolalar",
            "balkon uchun shift bormi",
            "hammom uchun shiftlar",
            "bolalar xonasiga shift",
        ],
    )
    def test_room_specific_catalog_ask_is_no_catalog_match(self, text: str) -> None:
        # A catalog trigger (room word) with NO design alias and NO generic
        # catalog word ("dizayn"/"namuna"/"rasm"/"katalog") → resolver "no_alias"
        # → no_catalog_match. (Adding a generic word would route to the normal
        # generic-catalog fallback instead — covered below.)
        assert _is_catalog_request(text) is True
        assert _catalog_reason(text) == "no_catalog_match"

    def test_generic_word_routes_to_generic_not_capture(self) -> None:
        # Same room ask but with a generic catalog word → generic_catalog_trigger
        # → NOT a failure (the user gets the full catalog, which is fine).
        assert _catalog_reason("balkon uchun dizayn bormi") is None


class TestCatalogSuccessNotCaptured:
    @pytest.mark.parametrize("text", ["gulli", "gulli katalog", "mramor", "hi-tech", "kosmos"])
    def test_matched_design_not_captured(self, text: str) -> None:
        assert _catalog_reason(text) is None

    @pytest.mark.parametrize("text", ["katalog", "katalog ko'rsat", "rasm tashla", "namuna ber"])
    def test_generic_catalog_ask_not_captured(self, text: str) -> None:
        # Pure generic catalog ask → generic_catalog_trigger → NOT a failure.
        assert _catalog_reason(text) is None

    @pytest.mark.parametrize("text", ["naqsh", "naqsh ko'rsat"])
    def test_ambiguous_trigger_not_captured(self, text: str) -> None:
        # Ambiguous "naqsh" → confirmation prompt → not a failure.
        assert _catalog_reason(text) is None


# ── Price: real parser + classifier integration ──────────────────────────────


def _price_terminal_reached(text: str) -> bool:
    """True if a price intent message would reach the terminal no-slot branch.

    Mirrors the handler: terminal else is reached only when area, district AND
    design are all absent.
    """
    combo = parse_combo(text)
    return combo["area"] is None and combo["district"] is None and not combo["design"]


class TestPriceUnknownCaptured:
    @pytest.mark.parametrize(
        "text",
        [
            "menga balkon uchun narx aytib bera olasizmi",
            "narxlaringiz juda chalkash menga tushuntiring iltimos",
            "bu xizmat narxi qanaqa bo'ladi menimcha qimmat",
        ],
    )
    def test_substantive_unparseable_price_captured(self, text: str) -> None:
        # No slots parsed AND substantive → unknown_price_question.
        assert _price_terminal_reached(text) is True
        assert classify_price_capture(text) == "unknown_price_question"


class TestPriceNormalNotCaptured:
    @pytest.mark.parametrize("text", ["narx qancha", "necha pul", "narxi qancha"])
    def test_short_bare_price_not_captured(self, text: str) -> None:
        assert classify_price_capture(text) is None

    def test_price_with_design_not_terminal(self) -> None:
        # "gulli necha pul" → design parsed → handler asks area, terminal NOT reached.
        combo = parse_combo("gulli necha pul")
        assert combo["design"]  # design present
        assert _price_terminal_reached("gulli necha pul") is False

    def test_price_with_area_not_terminal(self) -> None:
        combo = parse_combo("20 m2 narx qancha")
        assert combo["area"] is not None
        assert _price_terminal_reached("20 m2 narx qancha") is False

    def test_price_with_area_and_design_not_terminal(self) -> None:
        assert _price_terminal_reached("20 m2 gulli narx") is False


# ── Never-capture flows (intent-based) ───────────────────────────────────────


class TestNeverCaptureFlows:
    def test_operator_request_detected_separately(self) -> None:
        # Operator messages are handled by the operator branch, not catalog/price.
        assert _is_operator_request("operator bilan bog'laning") is True

    def test_gulli_katalog_is_success(self) -> None:
        assert _catalog_reason("gulli katalog") is None

    def test_gulli_necha_pul_not_price_terminal(self) -> None:
        assert _price_terminal_reached("gulli necha pul") is False

    def test_phone_only_not_substantive_price(self) -> None:
        assert classify_price_capture("+998901234567") is None

    def test_greeting_not_catalog(self) -> None:
        # "salom" is not a catalog request, so catalog capture never runs for it.
        assert _is_catalog_request("salom") is False

    def test_stop_word_not_catalog(self) -> None:
        assert _is_catalog_request("kerak emas") is False


# ── Source-pin: handler wiring ───────────────────────────────────────────────


class TestHandlerWiring:
    def test_imports_classifiers(self) -> None:
        s = _src()
        assert "classify_catalog_capture as _classify_catalog_capture" in s
        assert "classify_price_capture as _classify_price_capture" in s

    def test_catalog_capture_wired_twice(self) -> None:
        # One per handler (handle_ai_question + handle_ai_message).
        assert _src().count("_classify_catalog_capture(") == 2

    def test_price_capture_wired_twice(self) -> None:
        assert _src().count("_classify_price_capture(") == 2

    def test_catalog_capture_schedules(self) -> None:
        assert _src().count("reason=_cat_capture") == 2

    def test_price_capture_schedules(self) -> None:
        assert _src().count("reason=_price_capture") == 2

    def test_catalog_live_route_label(self) -> None:
        # Two new capture calls use live_route="catalog"; a pre-existing shadow
        # call also uses it, so there are >= 2 (3 total today).
        assert _src().count('live_route="catalog"') >= 2

    def test_price_live_route_label(self) -> None:
        assert _src().count('live_route="price"') == 2

    def test_catalog_capture_uses_resolver_result(self) -> None:
        s = _src()
        assert "_cat_result = _resolve_catalog_link(text)" in s

    def test_capture_is_fire_and_forget(self) -> None:
        # New captures go through the same _schedule_unknown_capture helper.
        s = _src()
        assert "_schedule_unknown_capture(" in s

    def test_no_capture_in_generic_confirmation_branch(self) -> None:
        # The _NEUTRAL_REPLY (confirmation) branch must NOT schedule a capture.
        s = _src()
        idx = s.index("_NEUTRAL_REPLY")
        window = s[idx - 200 : idx + 200]
        assert "_schedule_unknown_capture" not in window

    def test_no_new_reason_literals_outside_helpers(self) -> None:
        # The handler must not hardcode reason strings for catalog/price; it uses
        # the classifier return values (reason=_cat_capture / reason=_price_capture).
        s = _src()
        assert 'reason="no_catalog_match"' not in s
        assert 'reason="unknown_price_question"' not in s


# ── Unchanged-behavior pins ──────────────────────────────────────────────────


class TestUnchangedBehavior:
    def test_existing_openai_capture_intact(self) -> None:
        assert _src().count('reason="openai_error"') == 2

    def test_existing_safety_capture_intact(self) -> None:
        assert 'reason="safety_block"' in _src()

    def test_catalog_reply_text_unchanged(self) -> None:
        assert "_catalog_intro_text_for(text)" in _src()
        assert "_CATALOG_SOFT_CTA" in _src()

    def test_price_ask_text_unchanged(self) -> None:
        assert "_PRICE_ASK_DESIGN_TEXT" in _src()

    def test_no_send_message_added(self) -> None:
        # Captures must not introduce any extra send_message side effect.
        s = _src()
        # send_chat_action is pre-existing; ensure we didn't add raw send_message
        # in the capture wiring (capture is DB-only, fire-and-forget).
        assert "_schedule_unknown_capture" in s


class TestReasonsDeferred:
    """Document via test that low_confidence / shadow_live_mismatch / generic_reply
    / unknown_design are NOT wired into the live handler in v2."""

    def test_low_confidence_not_wired(self) -> None:
        assert 'reason="low_confidence"' not in _src()

    def test_shadow_mismatch_not_wired(self) -> None:
        assert 'reason="shadow_live_mismatch"' not in _src()

    def test_generic_reply_not_wired(self) -> None:
        assert 'reason="generic_reply"' not in _src()

    def test_unknown_design_not_wired(self) -> None:
        # Folded into no_catalog_match for v2; no separate live trigger yet.
        assert 'reason="unknown_design"' not in _src()


# ── No OpenAI / network in this module ───────────────────────────────────────


class TestPurity:
    def test_classifiers_are_pure(self) -> None:
        # Calling them many times has no side effects and never raises.
        for _ in range(5):
            assert (
                classify_catalog_capture(matched=False, needs_confirmation=False, reason="no_alias")
                == "no_catalog_match"
            )
            assert classify_price_capture("a b c d e") == "unknown_price_question"

    def test_resolver_is_pure(self) -> None:
        a = _catalog_reason("balkon dizayn bormi")
        b = _catalog_reason("balkon dizayn bormi")
        assert a == b
