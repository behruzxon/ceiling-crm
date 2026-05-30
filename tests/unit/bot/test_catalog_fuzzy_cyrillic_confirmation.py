"""Catalog fuzzy + Cyrillic + confirmation UX tests.

Covers the upgraded resolver, the Cyrillic-aware price-intent guard,
and the confirmation callback wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.bot.handlers.private.ai_detection import _is_price_query
from core.schemas.catalog_link import CatalogLink, CatalogLinkResult
from core.services.catalog_link_resolver_service import resolve_catalog_link
from shared.constants.catalog import CATALOG_BY_KEY
from shared.utils.text_normalization import (
    latinize_uz_cyrillic,
    normalize_customer_text,
)

# ── Normalization helpers ──────────────────────────────────────────────


class TestLatinize:
    def test_empty(self) -> None:
        assert latinize_uz_cyrillic("") == ""
        assert latinize_uz_cyrillic(None) == ""

    def test_lowercase(self) -> None:
        assert "guli" in latinize_uz_cyrillic("ГУЛИ")

    def test_gulli(self) -> None:
        assert "gulli" in latinize_uz_cyrillic("гулли")

    def test_marmar(self) -> None:
        assert "marmar" in latinize_uz_cyrillic("мармар")

    def test_mramor(self) -> None:
        assert "mramor" in latinize_uz_cyrillic("мрамор")

    def test_hi_tek(self) -> None:
        assert "hi tech" in latinize_uz_cyrillic("хай тек")

    def test_xaytek(self) -> None:
        assert "hitech" in latinize_uz_cyrillic("хайтек")

    def test_kosmos(self) -> None:
        assert "kosmos" in latinize_uz_cyrillic("космос")

    def test_osmon(self) -> None:
        assert "osmon" in latinize_uz_cyrillic("осмон")

    def test_oshxona(self) -> None:
        assert "oshxona" in latinize_uz_cyrillic("ошхона")

    def test_naqsh(self) -> None:
        assert "naqsh" in latinize_uz_cyrillic("нақш")

    def test_oq(self) -> None:
        assert "oq" in latinize_uz_cyrillic("оқ")

    def test_qora(self) -> None:
        assert "qora" in latinize_uz_cyrillic("қора")

    def test_uf(self) -> None:
        assert "uf" in latinize_uz_cyrillic("уф")

    def test_pechat(self) -> None:
        assert "pechat" in latinize_uz_cyrillic("печать")


class TestNormalize:
    def test_apostrophe_unified(self) -> None:
        for variant in ("ʻ", "‘", "’", "`"):
            n = normalize_customer_text(f"to{variant}liq")
            assert "to'liq" in n

    def test_whitespace_collapsed(self) -> None:
        assert normalize_customer_text("a   b\n c") == "a b c"

    def test_lowercased(self) -> None:
        assert normalize_customer_text("KATALOG") == "katalog"

    def test_latinize_enabled_by_default(self) -> None:
        assert "katalog" in normalize_customer_text("Каталог")


# ── Direct alias resolution (Latin) ────────────────────────────────────


class TestLatinAliases:
    def test_gulli(self) -> None:
        r = resolve_catalog_link("gulli katalog")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_guli(self) -> None:
        r = resolve_catalog_link("guli katalog")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_gullli_typo(self) -> None:
        # Triple-l typo is in the alias list → direct match.
        r = resolve_catalog_link("gullli katalog")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_mramor(self) -> None:
        r = resolve_catalog_link("mramor katalog")
        assert r.matched and r.link and r.link.key == "mramor"

    def test_marmar(self) -> None:
        r = resolve_catalog_link("marmar katalog")
        assert r.matched and r.link and r.link.key == "mramor"

    def test_hi_tek(self) -> None:
        r = resolve_catalog_link("hi tek katalog")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_xaytek(self) -> None:
        r = resolve_catalog_link("xaytek katalog")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_kuxnya(self) -> None:
        r = resolve_catalog_link("kuxnya katalog")
        assert r.matched and r.link and r.link.key == "oshxona"

    def test_oshhona(self) -> None:
        r = resolve_catalog_link("oshhona katalog")
        assert r.matched and r.link and r.link.key == "oshxona"


# ── Cyrillic resolution ────────────────────────────────────────────────


class TestCyrillicResolution:
    def test_guli_cyr(self) -> None:
        r = resolve_catalog_link("гули каталог")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_gulli_cyr(self) -> None:
        r = resolve_catalog_link("гулли каталог")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_marmar_cyr(self) -> None:
        r = resolve_catalog_link("мармар каталог")
        assert r.matched and r.link and r.link.key == "mramor"

    def test_mramor_cyr(self) -> None:
        r = resolve_catalog_link("мрамор каталог")
        assert r.matched and r.link and r.link.key == "mramor"

    def test_hi_tek_cyr(self) -> None:
        r = resolve_catalog_link("хай тек каталог")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_kosmos_cyr(self) -> None:
        r = resolve_catalog_link("космос каталог")
        assert r.matched and r.link and r.link.key == "kosmos"

    def test_osmon_cyr(self) -> None:
        r = resolve_catalog_link("осмон каталог")
        assert r.matched and r.link and r.link.key == "osmon"

    def test_oshxona_cyr(self) -> None:
        r = resolve_catalog_link("ошхона каталог")
        assert r.matched and r.link and r.link.key == "oshxona"

    def test_qora_naqsh_cyr(self) -> None:
        r = resolve_catalog_link("қора нақш каталог")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_uf_pechat_cyr(self) -> None:
        r = resolve_catalog_link("уф печать каталог")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_naqsh_oq_cyr(self) -> None:
        r = resolve_catalog_link("нақш оқ каталог")
        assert r.matched and r.link and r.link.key == "naqsh_oq"

    def test_kora_naks_cyr_typo(self) -> None:
        r = resolve_catalog_link("кора накш каталог")
        # latinizes to "kora naks katalog" — matches "kora naks" alias
        # which is registered under qora_naqsh_uf.
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_cyr_confidence_is_95(self) -> None:
        r = resolve_catalog_link("гулли")
        assert r.confidence == 95


# ── Ambiguity / confirmation ───────────────────────────────────────────


class TestAmbiguous:
    def test_bare_naqsh_needs_confirmation(self) -> None:
        r = resolve_catalog_link("naqsh katalog")
        assert r.matched is False
        assert r.needs_confirmation is True
        keys = {c.key for c in r.candidates}
        assert keys == {"naqsh_oq", "naqsh_ramka", "qora_naqsh_uf"}

    def test_bare_naqsh_returns_confirmation_question(self) -> None:
        r = resolve_catalog_link("naqsh katalog")
        assert r.confirmation_question

    def test_bare_naqsh_cyr_needs_confirmation(self) -> None:
        r = resolve_catalog_link("нақш каталог")
        assert r.needs_confirmation is True

    def test_naqsh_oq_beats_bare_naqsh(self) -> None:
        r = resolve_catalog_link("naqsh oq katalog")
        assert r.matched is True
        assert r.link is not None and r.link.key == "naqsh_oq"

    def test_naqsh_ramka_direct(self) -> None:
        r = resolve_catalog_link("naqsh ramka katalog")
        assert r.matched and r.link and r.link.key == "naqsh_ramka"


# ── Fuzzy edit-distance fallback ───────────────────────────────────────


class TestFuzzyMatch:
    def test_far_typo_returns_match_or_confirmation(self) -> None:
        # "mramorr" with extra r — close enough to direct match.
        r = resolve_catalog_link("mramorr katalog")
        assert r.matched is True or r.needs_confirmation is True
        if r.matched:
            assert r.link is not None and r.link.key == "mramor"

    def test_random_word_no_match(self) -> None:
        r = resolve_catalog_link("foobarbaz")
        assert r.matched is False
        assert r.needs_confirmation is False


# ── Generic / negative paths ───────────────────────────────────────────


class TestGenericFallback:
    def test_katalog_tashla_generic(self) -> None:
        r = resolve_catalog_link("katalog tashla")
        assert r.matched is False
        assert r.fallback_link is not None
        assert r.fallback_link.url == "https://t.me/vashpotolokuz"

    def test_rasm_korsat_generic(self) -> None:
        r = resolve_catalog_link("rasm ko'rsat")
        assert r.matched is False
        assert r.fallback_link is not None

    def test_dizaynlar_generic(self) -> None:
        r = resolve_catalog_link("dizaynlar")
        assert r.matched is False
        assert r.fallback_link is not None

    def test_empty(self) -> None:
        r = resolve_catalog_link("")
        assert r.matched is False
        assert r.fallback_link is not None
        assert r.reason == "empty_text"


# ── Price priority preserved ───────────────────────────────────────────


class TestPricePriority:
    """The resolver itself doesn't know about price intent — the
    caller (ai_support.py) gates on `_is_price_query(text) or
    _is_price_query(latinize_uz_cyrillic(text))`. These tests pin
    that the price-keyword detection still works for both Latin
    and Cyrillic input."""

    def test_gulli_nech_pul_is_price(self) -> None:
        assert _is_price_query("gulli nech pul") is True

    def test_gulli_neech_pul_cyr_is_price(self) -> None:
        assert _is_price_query(latinize_uz_cyrillic("гулли неч пул")) is True

    def test_qancha_cyr_is_price(self) -> None:
        assert _is_price_query(latinize_uz_cyrillic("гулли қанча")) is True

    def test_narx_cyr_is_price(self) -> None:
        assert _is_price_query(latinize_uz_cyrillic("гулли нарх")) is True


# ── Caller wiring (source pin) ─────────────────────────────────────────


class TestAiSupportWiring:
    """Pin the actual source so a future edit can't silently revert
    the price guard or remove the new helpers."""

    @staticmethod
    def _src() -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_uses_latinize_in_guard(self) -> None:
        src = self._src()
        assert "_latinize_uz_cyrillic" in src
        assert "_is_price_query(_latinized)" in src

    def test_uses_build_catalog_link_kb(self) -> None:
        src = self._src()
        assert src.count("_build_catalog_link_kb(text)") >= 2

    def test_uses_catalog_intro_text_for(self) -> None:
        src = self._src()
        assert src.count("_catalog_intro_text_for(text)") >= 2

    def test_uses_price_intent_guard(self) -> None:
        src = self._src()
        assert src.count("not _price_intent_present") >= 2


# ── Confirmation callback router exists ───────────────────────────────


class TestConfirmCallbackRouter:
    def test_router_module_present(self) -> None:
        path = Path("apps/bot/handlers/callbacks/catalog_confirm_callbacks.py")
        assert path.is_file()
        src = path.read_text(encoding="utf-8")
        assert "catalog_confirm:" in src
        assert 'F.data == "catalog_all"' in src

    def test_router_registered_in_main(self) -> None:
        src = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "catalog_confirm_callbacks_router" in src

    def test_confirm_keyboard_used_for_ambiguous(self) -> None:
        from apps.bot.handlers.private.ai_support import _build_catalog_link_kb

        kb = _build_catalog_link_kb("naqsh katalog")
        callbacks = [
            btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data
        ]
        assert any(cb.startswith("catalog_confirm:naqsh_oq") for cb in callbacks)
        assert any(cb.startswith("catalog_confirm:naqsh_ramka") for cb in callbacks)
        assert any(cb.startswith("catalog_confirm:qora_naqsh_uf") for cb in callbacks)
        assert "catalog_all" in callbacks

    def test_url_button_for_high_confidence(self) -> None:
        from apps.bot.handlers.private.ai_support import _build_catalog_link_kb

        kb = _build_catalog_link_kb("gulli katalog")
        urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
        assert any(u == CATALOG_BY_KEY["gulli"].group_url for u in urls)


# ── URL safety / no invented links / no secrets ───────────────────────


class TestUrlSafety:
    _ALL = [
        "gulli",
        "guli",
        "gullli",
        "гули",
        "гулли",
        "мрамор",
        "marmar",
        "хай тек",
        "xaytek",
        "kuxnya",
        "ошхона",
        "naqsh oq",
        "naqsh ramka",
        "katalog tashla",
        "naqsh katalog",
        "mramorr",
        "foobarbaz",
    ]

    def test_every_url_is_tme(self) -> None:
        for q in self._ALL:
            r = resolve_catalog_link(q)
            for link in (r.link, r.fallback_link, *r.candidates):
                if link is None or not link.url:
                    continue
                assert link.url.startswith("https://t.me/"), (q, link.url)

    def test_every_matched_url_comes_from_canonical(self) -> None:
        for q in self._ALL:
            r = resolve_catalog_link(q)
            for link in (r.link, *r.candidates):
                if link is None or not link.url:
                    continue
                section = CATALOG_BY_KEY[link.key]
                assert link.url == section.group_url

    def test_no_secrets_in_resolver_output(self) -> None:
        for q in self._ALL + ["sk-leak", "Bearer abc1234", "postgres://x"]:
            blob = repr(resolve_catalog_link(q))
            for pat in (
                r"BOT_TOKEN",
                r"OPENAI",
                r"DATABASE_URL",
                r"Bearer\s+\S{8,}",
                r"sk-[A-Za-z0-9]{16,}",
                r"postgres://",
                r"redis://",
            ):
                assert re.search(pat, blob) is None, (q, pat)


# ── Dataclass invariants ──────────────────────────────────────────────


class TestFrozen:
    def test_result_is_frozen(self) -> None:
        r = CatalogLinkResult()
        try:
            r.matched = True  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("CatalogLinkResult should be frozen")

    def test_link_is_frozen(self) -> None:
        link = CatalogLink(key="x", title="X", url="https://t.me/x")
        try:
            link.key = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("CatalogLink should be frozen")

    def test_default_candidates_is_empty_tuple(self) -> None:
        assert CatalogLinkResult().candidates == ()


# ── Intent matrix smoke ───────────────────────────────────────────────


class TestIntentMatrix:
    cases = (
        # (query, expected_matched, expected_key_or_None, expected_needs_conf)
        ("гули каталог", True, "gulli", False),
        ("мрамор каталог", True, "mramor", False),
        ("хай тек каталог", True, "hi_tech", False),
        ("ошхона каталог", True, "oshxona", False),
        ("кора накш каталог", True, "qora_naqsh_uf", False),
        ("naqsh katalog", False, None, True),
        ("gullli katalog", True, "gulli", False),
        ("katalog tashla", False, None, False),
        ("operator kerak", False, None, False),
        ("kerak emas", False, None, False),
    )

    def test_each_row(self) -> None:
        for q, expected_matched, expected_key, expected_conf in self.cases:
            r = resolve_catalog_link(q)
            assert r.matched is expected_matched, (q, r)
            if expected_key:
                assert r.link is not None and r.link.key == expected_key, (q, r)
            assert r.needs_confirmation is expected_conf, (q, r)
