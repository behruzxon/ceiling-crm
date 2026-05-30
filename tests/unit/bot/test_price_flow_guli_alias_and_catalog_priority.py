"""Price-flow bug fix: ``guli`` alias + catalog/price priority.

Issue: "gulli nech pul" was routed to the catalog branch because
"gulli" is in ``_CATALOG_TRIGGERS`` and the catalog check ran before
the price-intent check. Also "guli" (single-l misspelling) was not
recognised as a design at all.

Fixes covered here:

1. ``_DESIGN_NAMES_IN_TEXT`` recognises ``guli`` and ``gul`` → Gulli.
2. ``PriceCalculatorService.parse_design_from_text`` recognises the
   same misspellings.
3. ``PriceCalculatorService.extract_and_respond`` returns a
   deterministic estimate for "20 kv gulli qancha" and
   "5x4 gulli qancha".
4. The catalog / operator routes still work for non-price text.

These tests only exercise pure detection + the deterministic price
calculator. No Telegram round-trips, no OpenAI calls.
"""

from __future__ import annotations

from apps.bot.handlers.private.ai_detection import (
    _CATALOG_DESIGN_KEYWORDS,
    _DESIGN_NAMES_IN_TEXT,
    _detect_catalog_context,
    _extract_design_from_text,
    _is_catalog_request,
    _is_price_query,
    parse_combo,
)
from core.services.price_calculator_service import PriceCalculatorService

# ── "guli" alias is now recognised ─────────────────────────────────────


class TestGuliAlias:
    def test_design_dict_contains_guli(self) -> None:
        assert "guli" in _DESIGN_NAMES_IN_TEXT
        assert _DESIGN_NAMES_IN_TEXT["guli"] == "Gulli"

    def test_design_dict_contains_gul(self) -> None:
        assert "gul" in _DESIGN_NAMES_IN_TEXT
        assert _DESIGN_NAMES_IN_TEXT["gul"] == "Gulli"

    def test_extract_design_guli(self) -> None:
        assert _extract_design_from_text("guli") == "Gulli"

    def test_extract_design_guli_inside_sentence(self) -> None:
        assert _extract_design_from_text("guli kerak") == "Gulli"

    def test_extract_design_gullili_still_works(self) -> None:
        assert _extract_design_from_text("gullili") == "Gulli"

    def test_parse_combo_guli_returns_gulli(self) -> None:
        combo = parse_combo("guli")
        assert combo["design"] == "Gulli"

    def test_catalog_context_resolves_guli(self) -> None:
        room, design = _detect_catalog_context("guli kerak")
        assert design == "Gulli"

    def test_catalog_design_keywords_contains_guli(self) -> None:
        assert _CATALOG_DESIGN_KEYWORDS.get("guli") == "Gulli"


# ── Price calculator alias parity ──────────────────────────────────────


class TestPriceCalculatorGuliAlias:
    svc = PriceCalculatorService()

    def test_parse_design_guli(self) -> None:
        assert PriceCalculatorService.parse_design_from_text("guli") == "gulli"

    def test_parse_design_guli_in_sentence(self) -> None:
        assert PriceCalculatorService.parse_design_from_text("20 m guli qancha") == "gulli"

    def test_parse_design_gullili_still_works(self) -> None:
        assert PriceCalculatorService.parse_design_from_text("gullili xona") == "gulli"


# ── Deterministic price estimate for combo queries ────────────────────


class TestDeterministicPriceEstimate:
    svc = PriceCalculatorService()

    def test_20_kv_gulli_qancha_returns_estimate(self) -> None:
        resp = self.svc.extract_and_respond("20 kv gulli qancha")
        assert resp.estimate is not None
        est = resp.estimate
        assert est.area_m2 == 20
        assert est.design_key == "gulli"
        assert est.is_estimate is True
        assert est.total_uzs > 0

    def test_5x4_gulli_qancha_returns_estimate(self) -> None:
        resp = self.svc.extract_and_respond("5x4 gulli qancha")
        assert resp.estimate is not None
        est = resp.estimate
        assert est.area_m2 == 20
        assert est.design_key == "gulli"
        assert est.is_estimate is True

    def test_20_kv_guli_qancha_returns_estimate(self) -> None:
        # Misspelling: only one 'l'
        resp = self.svc.extract_and_respond("20 kv guli qancha")
        assert resp.estimate is not None
        assert resp.estimate.design_key == "gulli"

    def test_estimate_user_text_says_taxminiy(self) -> None:
        resp = self.svc.extract_and_respond("20 kv gulli qancha")
        assert resp.user_text is not None
        assert "taxminiy" in resp.user_text.lower()

    def test_estimate_user_text_avoids_final_guarantee(self) -> None:
        resp = self.svc.extract_and_respond("20 kv gulli qancha")
        forbidden = ("kafolat", "100%", "darhol", "bugun")
        assert resp.user_text is not None
        text = resp.user_text.lower()
        for word in forbidden:
            assert word not in text


# ── Catalog routing priority — price-intent text must NOT hit catalog ──


class TestCatalogPriorityGuard:
    """Verify the routing-gate logic used in ai_support.handle_ai_*."""

    @staticmethod
    def _should_take_catalog_branch(text: str) -> bool:
        """Mirror of the new guard:
        ``if _is_catalog_request(text) and not (_is_price_query(text) or
        parse_combo(text)["area"] is not None)``.
        """
        return _is_catalog_request(text) and not (
            _is_price_query(text) or parse_combo(text)["area"] is not None
        )

    def test_gulli_nech_pul_skips_catalog(self) -> None:
        assert self._should_take_catalog_branch("gulli nech pul") is False

    def test_guli_nech_pul_skips_catalog(self) -> None:
        assert self._should_take_catalog_branch("guli nech pul") is False

    def test_20_gulli_qancha_skips_catalog(self) -> None:
        assert self._should_take_catalog_branch("20 m² gulli qancha") is False

    def test_5x4_gulli_skips_catalog(self) -> None:
        assert self._should_take_catalog_branch("5x4 gulli") is False

    def test_katalog_tashla_still_routes_to_catalog(self) -> None:
        assert self._should_take_catalog_branch("katalog tashla") is True

    def test_rasm_korsat_still_routes_to_catalog(self) -> None:
        assert self._should_take_catalog_branch("rasm ko'rsat") is True

    def test_gulli_dizayn_ko_rsat_routes_to_catalog(self) -> None:
        # "ko'rsat" is a catalog trigger; no price keyword → catalog wins.
        assert self._should_take_catalog_branch("gulli dizayn ko'rsat") is True

    def test_pure_design_word_alone_still_treated_as_catalog(self) -> None:
        # No price keyword, no area, just "gulli" → catalog (legacy
        # behaviour preserved; the guard only flips when price intent
        # is present).
        assert self._should_take_catalog_branch("gulli") is True

    def test_operator_kerak_not_caught_by_catalog(self) -> None:
        # Sanity: operator triggers do not touch our guard.
        assert _is_catalog_request("operator kerak") is False


# ── Routing source-of-truth check ──────────────────────────────────────


class TestAiSupportSourceUsesPriceGuard:
    """Pin the actual source so a future edit can't silently regress."""

    def test_handle_ai_question_uses_price_intent_guard(self) -> None:
        from pathlib import Path

        src = Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")
        assert "_price_intent_present" in src
        assert "not _price_intent_present" in src

    def test_price_design_persisted_to_fsm(self) -> None:
        from pathlib import Path

        src = Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")
        assert 'price_design=_combo["design"]' in src
