"""Catalog deep-link resolver tests.

Verifies that ``resolve_catalog_link`` maps each Uzbek alias to the
correct CatalogSection from ``shared.constants.catalog.CATALOG_BY_KEY``
and that the bot AI catalog branch wires the design-specific button
without breaking the price-intent guard added by F-fix ea3d5f8.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.schemas.catalog_link import CatalogLink, CatalogLinkResult
from core.services.catalog_link_resolver_service import resolve_catalog_link
from shared.constants.catalog import CATALOG_BY_KEY

# ── Design resolution ──────────────────────────────────────────────────


class TestResolveGulli:
    def test_gulli_exact(self) -> None:
        r = resolve_catalog_link("gulli katalog tashla")
        assert r.matched is True
        assert r.link is not None
        assert r.link.key == "gulli"
        assert r.link.url == CATALOG_BY_KEY["gulli"].group_url

    def test_guli_misspelling(self) -> None:
        r = resolve_catalog_link("guli bormi")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_gul_short(self) -> None:
        r = resolve_catalog_link("gul ko'rsat")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_gullili(self) -> None:
        r = resolve_catalog_link("gullili xona uchun")
        assert r.matched and r.link and r.link.key == "gulli"


class TestResolveOdnotonniy:
    def test_odnotonniy(self) -> None:
        r = resolve_catalog_link("odnotonniy katalog")
        assert r.matched and r.link and r.link.key == "odnotonniy"

    def test_adnatonniy_alias(self) -> None:
        r = resolve_catalog_link("adnatonniy bormi")
        assert r.matched and r.link and r.link.key == "odnotonniy"

    def test_oddiy(self) -> None:
        r = resolve_catalog_link("oddiy dizayn ko'rsat")
        assert r.matched and r.link and r.link.key == "odnotonniy"

    def test_matt(self) -> None:
        r = resolve_catalog_link("matt katalog")
        assert r.matched and r.link and r.link.key == "odnotonniy"


class TestResolveMramor:
    def test_mramor(self) -> None:
        r = resolve_catalog_link("mramor katalog")
        assert r.matched and r.link and r.link.key == "mramor"

    def test_marble(self) -> None:
        r = resolve_catalog_link("marble bormi")
        assert r.matched and r.link and r.link.key == "mramor"


class TestResolveHiTech:
    def test_hitech_compact(self) -> None:
        r = resolve_catalog_link("hitech katalog")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_hi_tech_spaced(self) -> None:
        r = resolve_catalog_link("hi tech katalog")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_hi_dash_tech(self) -> None:
        r = resolve_catalog_link("hi-tech ko'rsat")
        assert r.matched and r.link and r.link.key == "hi_tech"

    def test_led_alias(self) -> None:
        r = resolve_catalog_link("led katalog")
        assert r.matched and r.link and r.link.key == "hi_tech"


class TestResolveKosmos:
    def test_kosmos(self) -> None:
        r = resolve_catalog_link("kosmos ko'rsat")
        assert r.matched and r.link and r.link.key == "kosmos"


class TestResolveOsmon:
    def test_osmon(self) -> None:
        r = resolve_catalog_link("osmon dizayn ko'rsat")
        assert r.matched and r.link and r.link.key == "osmon"


class TestResolveOshxona:
    def test_oshxona(self) -> None:
        r = resolve_catalog_link("oshxona uchun katalog")
        assert r.matched and r.link and r.link.key == "oshxona"

    def test_kuxnya_ru_alias(self) -> None:
        r = resolve_catalog_link("kuxnya katalog")
        assert r.matched and r.link and r.link.key == "oshxona"

    def test_kitchen_en_alias(self) -> None:
        r = resolve_catalog_link("kitchen catalog")
        assert r.matched and r.link and r.link.key == "oshxona"


class TestResolveQoraNaqsh:
    def test_qora_naqsh(self) -> None:
        r = resolve_catalog_link("qora naqsh ko'rsat")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_qora_uf(self) -> None:
        r = resolve_catalog_link("qora uf bormi")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_uf_pechat(self) -> None:
        r = resolve_catalog_link("uf pechat katalog")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"

    def test_pechat_alone(self) -> None:
        r = resolve_catalog_link("pechat dizayn")
        assert r.matched and r.link and r.link.key == "qora_naqsh_uf"


class TestResolveNaqshRamka:
    def test_naqsh_ramka(self) -> None:
        r = resolve_catalog_link("naqsh ramka katalog")
        assert r.matched and r.link and r.link.key == "naqsh_ramka"


class TestResolveNaqshOq:
    def test_naqsh_oq(self) -> None:
        r = resolve_catalog_link("naqsh oq ko'rsat")
        assert r.matched and r.link and r.link.key == "naqsh_oq"

    def test_naqsh_oq_beats_bare_naqsh(self) -> None:
        # "naqsh oq" must win over the bare "naqsh" alias.
        r = resolve_catalog_link("naqsh oq dizayn")
        assert r.link is not None and r.link.key == "naqsh_oq"


# ── Generic fallback ───────────────────────────────────────────────────


class TestGenericFallback:
    def test_katalog_tashla(self) -> None:
        r = resolve_catalog_link("katalog tashla")
        assert r.matched is False
        assert r.fallback_link is not None
        assert r.fallback_link.url == "https://t.me/vashpotolokuz"

    def test_rasm_korsat(self) -> None:
        r = resolve_catalog_link("rasm ko'rsat")
        assert r.matched is False
        assert r.fallback_link is not None

    def test_dizaynlar_only(self) -> None:
        r = resolve_catalog_link("dizaynlar")
        assert r.matched is False

    def test_empty_text(self) -> None:
        r = resolve_catalog_link("")
        assert r.matched is False
        assert r.reason == "empty_text"

    def test_none_text(self) -> None:
        r = resolve_catalog_link(None)
        assert r.matched is False
        assert r.reason == "empty_text"

    def test_fallback_link_present_in_no_match(self) -> None:
        r = resolve_catalog_link("hech narsa")
        assert r.fallback_link is not None and r.fallback_link.url


# ── Safety: returned URLs are real t.me links from CATALOG ─────────────


class TestUrlSafety:
    _ALL_QUERIES = [
        "gulli",
        "guli",
        "mramor",
        "kosmos",
        "osmon",
        "oshxona",
        "hi tech",
        "hi-tech",
        "qora naqsh",
        "naqsh oq",
        "naqsh ramka",
        "odnotonniy",
        "katalog tashla",
    ]

    def test_every_returned_url_is_https_or_tme(self) -> None:
        for q in self._ALL_QUERIES:
            r = resolve_catalog_link(q)
            for link in (r.link, r.fallback_link):
                if link is None:
                    continue
                if not link.url:
                    continue
                assert link.url.startswith("https://t.me/"), f"{q!r} → {link.url!r}"

    def test_no_secrets_in_resolver_output(self) -> None:
        for q in self._ALL_QUERIES + ["sk-leak", "Bearer abc", "postgres://x"]:
            r = resolve_catalog_link(q)
            blob = repr(r)
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

    def test_no_fake_invented_urls(self) -> None:
        # Every matched URL must equal the canonical CATALOG entry.
        for q in (
            "gulli",
            "mramor",
            "kosmos",
            "osmon",
            "oshxona",
            "hi tech",
            "qora naqsh",
            "naqsh oq",
            "naqsh ramka",
            "odnotonniy",
        ):
            r = resolve_catalog_link(q)
            assert r.link is not None
            section = CATALOG_BY_KEY[r.link.key]
            assert r.link.url == section.group_url

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


# ── Price intent must NOT route through resolver as final action ───────


class TestPriceIntentStillWins:
    """The resolver itself is intent-agnostic — it'll happily map
    "gulli nech pul" to Gulli. The *caller* (ai_support.py) is
    responsible for letting the price flow win. These tests pin the
    guard in the source so it can't regress silently."""

    def test_handle_uses_price_intent_guard(self) -> None:
        src = Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")
        # Two catalog branches, two guards.
        assert src.count("not _price_intent_present") >= 2

    def test_handle_uses_resolver_helper(self) -> None:
        src = Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")
        # The new helper is called from both catalog branches.
        assert src.count("_build_catalog_link_kb(text)") >= 2
        assert src.count("_catalog_intro_text_for(text)") >= 2

    def test_helper_returns_design_specific_for_gulli(self) -> None:
        from apps.bot.handlers.private.ai_support import _build_catalog_link_kb

        kb = _build_catalog_link_kb("gulli katalog tashla")
        urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
        assert any("vashpotolokuz/2" in u for u in urls)

    def test_helper_returns_generic_for_pure_catalog(self) -> None:
        from apps.bot.handlers.private.ai_support import _build_catalog_link_kb

        kb = _build_catalog_link_kb("katalog tashla")
        urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
        # Generic root URL only (no /<id> suffix).
        assert any(u.rstrip("/") == "https://t.me/vashpotolokuz" for u in urls)

    def test_helper_uses_section_url_for_mramor(self) -> None:
        from apps.bot.handlers.private.ai_support import _build_catalog_link_kb

        kb = _build_catalog_link_kb("mramor katalog")
        urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
        assert any(u == CATALOG_BY_KEY["mramor"].group_url for u in urls)


# ── Regression: operator / stop / measurement unaffected ───────────────


class TestNoSideEffectsOnOtherIntents:
    def test_operator_kerak_no_match(self) -> None:
        r = resolve_catalog_link("operator kerak")
        assert r.matched is False

    def test_kerak_emas_no_match(self) -> None:
        r = resolve_catalog_link("kerak emas")
        assert r.matched is False

    def test_olchov_kerak_no_match(self) -> None:
        r = resolve_catalog_link("o'lchov kerak")
        assert r.matched is False


# ── Intent-coverage matrix ─────────────────────────────────────────────


class TestIntentMatrix:
    cases = (
        ("gulli katalog tashla", True, "gulli"),
        ("guli bormi", True, "gulli"),
        ("mramor katalog", True, "mramor"),
        ("oshxona uchun katalog", True, "oshxona"),
        ("kosmos ko'rsat", True, "kosmos"),
        ("osmon dizayn ko'rsat", True, "osmon"),
        ("hi tech katalog", True, "hi_tech"),
        ("qora naqsh bormi", True, "qora_naqsh_uf"),
        ("naqsh oq", True, "naqsh_oq"),
        ("naqsh ramka", True, "naqsh_ramka"),
        ("katalog tashla", False, None),
        ("rasm ko'rsat", False, None),
    )

    def test_each_case(self) -> None:
        for text, should_match, expected_key in self.cases:
            r = resolve_catalog_link(text)
            assert r.matched is should_match, (text, r)
            if should_match:
                assert r.link is not None and r.link.key == expected_key, (text, r)
            else:
                assert r.fallback_link is not None
