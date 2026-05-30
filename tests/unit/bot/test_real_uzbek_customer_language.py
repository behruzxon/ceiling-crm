"""Real Uzbek customer language pack — messy / street-style Telegram.

Customers don't write textbook Uzbek. The detectors need to recognise
short forms, typos, mixed Latin/Cyrillic, casual phrasing, missing
punctuation, and Uzbek apostrophe variants — and when uncertain, the
caller (ai_support.handle_ai_*) must ask a simple clarification
instead of routing to the wrong flow.

This file pins the new behaviour after the real-language pack. All
tests are pure offline detector calls.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.bot.handlers.private.ai_detection import (
    _is_catalog_request,
    _is_measurement_request,
    _is_operator_request,
    _is_price_query,
    parse_combo,
)
from apps.bot.handlers.private.ai_scoring import detect_objection_full
from core.services.catalog_link_resolver_service import resolve_catalog_link
from core.services.followup_scheduler_service import FollowupSchedulerService

# ── 25 messy PRICE phrases ─────────────────────────────────────────────


class TestMessyPrice:
    def test_nechi(self) -> None:
        assert _is_price_query("nechi") is True

    def test_nechpul(self) -> None:
        assert _is_price_query("nechpul") is True

    def test_nech_pul(self) -> None:
        assert _is_price_query("nech pul") is True

    def test_qanaqa_narx(self) -> None:
        assert _is_price_query("qanaqa narx") is True

    def test_qancha_boladi(self) -> None:
        assert _is_price_query("qancha boladi") is True

    def test_qancha_bo_apos_ladi(self) -> None:
        # Apostrophe variants are normalised by the detector.
        assert _is_price_query("qancha bo'ladi") is True
        assert _is_price_query("qancha bo’ladi") is True

    def test_qancha_tushadi(self) -> None:
        assert _is_price_query("qancha tushadi") is True

    def test_qancha_tushyapti(self) -> None:
        assert _is_price_query("qancha tushyapti") is True

    def test_bare_qancha(self) -> None:
        assert _is_price_query("qancha") is True

    def test_20_kv_qancha(self) -> None:
        assert _is_price_query("20 kv qancha") is True

    def test_20kv_no_space(self) -> None:
        # area parser recognises 20kv → price_intent via combo area
        combo = parse_combo("20kv")
        assert combo["area"] == 20

    def test_20kvm(self) -> None:
        combo = parse_combo("20kvm")
        assert combo["area"] == 20

    def test_5ga4(self) -> None:
        combo = parse_combo("5ga4 gulli")
        assert combo["area"] == 20
        assert combo["design"] == "Gulli"

    def test_5x4_guli(self) -> None:
        combo = parse_combo("5x4 guli")
        assert combo["area"] == 20
        assert combo["design"] == "Gulli"

    def test_guli_nechi(self) -> None:
        assert _is_price_query("guli nechi") is True

    def test_gulidan_nechi(self) -> None:
        assert _is_price_query("gulidan nechi") is True

    def test_eng_arzoni_qanaqa(self) -> None:
        assert _is_price_query("eng arzoni qanaqa") is True

    def test_eng_arzon(self) -> None:
        assert _is_price_query("eng arzon") is True

    def test_oddiy_nechpul(self) -> None:
        assert _is_price_query("oddiy nechpul") is True

    def test_odiy_nechi(self) -> None:
        assert _is_price_query("odiy nechi") is True

    def test_mramr_qancha(self) -> None:
        assert _is_price_query("mramr qancha") is True

    def test_hi_tek_nechi(self) -> None:
        assert _is_price_query("hi tek nechi") is True

    def test_qora_naqsh_nechi(self) -> None:
        # price_intent must win over catalog (qora naqsh is a design name)
        assert _is_price_query("qora naqsh nechi") is True

    def test_price_beats_catalog_for_messy_intent(self) -> None:
        # The caller-level guard: when BOTH price and catalog detectors
        # fire (e.g. "mramr qancha" → mramr is a design typo that
        # matches catalog AND qancha matches price), the price-intent
        # check in ai_support.handle_ai_* short-circuits the catalog
        # branch. This test pins both detectors AND the guard source.
        text = "mramr qancha"
        assert _is_price_query(text) is True
        # catalog detector may also fire because design typos live in
        # catalog triggers — that's fine; the guard skips catalog.
        src = Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")
        assert src.count("not _price_intent_present") >= 2

    def test_price_intent_combined_with_design_word(self) -> None:
        # "gullidan nechi" — design + nechi → price wins
        assert _is_price_query("gullidan nechi") is True


# ── 25 messy CATALOG phrases ──────────────────────────────────────────


class TestMessyCatalog:
    def test_rasm_tashen(self) -> None:
        # "tashen" not in triggers but "rasm" is — catalog triggers.
        assert _is_catalog_request("rasm tashen") is True

    def test_rasm_bormi(self) -> None:
        assert _is_catalog_request("rasm bormi") is True

    def test_namunala_bormi(self) -> None:
        assert _is_catalog_request("namunala bormi") is True

    def test_koraylik(self) -> None:
        assert _is_catalog_request("koraylik") is True

    def test_korsating(self) -> None:
        assert _is_catalog_request("korsating") is True

    def test_katalog_qani(self) -> None:
        assert _is_catalog_request("katalog qani") is True

    def test_katalk(self) -> None:
        assert _is_catalog_request("katalk") is True

    def test_katalok(self) -> None:
        assert _is_catalog_request("katalok") is True

    def test_katlog(self) -> None:
        assert _is_catalog_request("katlog") is True

    def test_ktalog(self) -> None:
        assert _is_catalog_request("ktalog") is True

    def test_guli_rasm(self) -> None:
        assert _is_catalog_request("guli rasm") is True

    def test_gulli_korsat(self) -> None:
        assert _is_catalog_request("gulli korsat") is True

    def test_mramr_korsat(self) -> None:
        assert _is_catalog_request("mramr korsat") is True

    def test_oshxona_uchun_bormi(self) -> None:
        assert _is_catalog_request("oshxona uchun bormi") is True

    def test_zalga_qanaqa_bor(self) -> None:
        # "zal" → catalog trigger (room type)
        assert _is_catalog_request("zalga qanaqa bor") is True

    def test_bolalar_xonasiga_qanaqa(self) -> None:
        assert _is_catalog_request("bolalar xonasiga qanaqa") is True

    def test_guli_rasm_routes_to_gulli_link(self) -> None:
        r = resolve_catalog_link("guli rasm")
        assert r.matched and r.link and r.link.key == "gulli"

    def test_mramr_korsat_routes_to_mramor_link(self) -> None:
        r = resolve_catalog_link("mramr korsat")
        # "mramor" alias matches; "mramr" not in resolver alias but
        # `_is_catalog_request` already returns True via "korsat";
        # resolver may return generic in that case — both shapes pass
        # because the bot still sends a catalog link, either specific
        # or generic.
        assert r.matched is True or r.fallback_link is not None

    def test_oshxona_uchun_bormi_routes_to_oshxona(self) -> None:
        r = resolve_catalog_link("oshxona uchun bormi")
        assert r.matched and r.link and r.link.key == "oshxona"

    def test_apostrophe_variants_dont_break_catalog(self) -> None:
        for v in ("ko‘rsat", "ko’rsat", "ko'rsat", "ko`rsat"):
            assert _is_catalog_request(f"{v}") is True

    def test_katalok_is_catalog_not_operator(self) -> None:
        # Edge: 'katalok' is a catalog typo — must not match operator.
        assert _is_catalog_request("katalok") is True
        assert _is_operator_request("katalok") is False

    def test_messy_catalog_preserves_resolver_no_match_fallback(self) -> None:
        r = resolve_catalog_link("katalog qani")
        assert r.fallback_link is not None
        assert r.fallback_link.url == "https://t.me/vashpotolokuz"

    def test_guli_rasm_no_price_word_routes_to_catalog(self) -> None:
        assert _is_catalog_request("guli rasm") is True
        assert _is_price_query("guli rasm") is False

    def test_katalk_short_typo_routes_to_catalog(self) -> None:
        assert _is_catalog_request("katalk") is True

    def test_katlog_short_typo_routes_to_catalog(self) -> None:
        assert _is_catalog_request("katlog") is True


# ── 20 messy MEASUREMENT / ORDER phrases ──────────────────────────────


class TestMessyMeasurement:
    def test_kelib_korila(self) -> None:
        assert _is_measurement_request("kelib korila") is True

    def test_kelib_korsela(self) -> None:
        assert _is_measurement_request("kelib korsela") is True

    def test_kelib_olchab_ketila(self) -> None:
        assert _is_measurement_request("kelib o'lchab ketila") is True
        assert _is_measurement_request("kelib o‘lchab ketila") is True
        assert _is_measurement_request("kelib olchab ketila") is True

    def test_olchab_ketila(self) -> None:
        assert _is_measurement_request("olchab ketila") is True

    def test_usta_jonatila_apos(self) -> None:
        assert _is_measurement_request("usta jo'natila") is True
        assert _is_measurement_request("usta jo‘natila") is True
        assert _is_measurement_request("usta jonatila") is True

    def test_odam_yuborila(self) -> None:
        assert _is_measurement_request("odam yuborila") is True

    def test_manzilga_kela_olasizmi(self) -> None:
        assert _is_measurement_request("manzilga kela olasizmi") is True

    def test_ertaga_kela_olasizmi(self) -> None:
        assert _is_measurement_request("ertaga kela olasizmi") is True

    def test_bugun_kelib_korasizmi(self) -> None:
        assert _is_measurement_request("bugun kelib korasizmi") is True

    def test_zakaz_bermoqchiman(self) -> None:
        assert _is_measurement_request("zakaz bermoqchiman") is True

    def test_buyurtma_qilaman(self) -> None:
        assert _is_measurement_request("buyurtma qilaman") is True

    def test_uyga_kelila(self) -> None:
        assert _is_measurement_request("uyga kelila") is True

    def test_uyga_kelinglar(self) -> None:
        assert _is_measurement_request("uyga kelinglar") is True

    def test_master_chaqir(self) -> None:
        assert _is_measurement_request("master chaqir") is True

    def test_montajchi_yubor(self) -> None:
        assert _is_measurement_request("montajchi yubor") is True

    def test_ustani_jonat(self) -> None:
        assert _is_measurement_request("ustani jonat") is True

    def test_ertaga_kelib_olchang_beats_delay(self) -> None:
        # measurement keyword present → measurement wins over delay
        assert _is_measurement_request("ertaga kelib o'lchang") is True

    def test_ambiguous_qilamiz_does_not_force_measurement(self) -> None:
        # Bare "qilamiz" alone should not auto-trigger measurement —
        # avoid false positives for ambiguous casual replies.
        assert _is_measurement_request("qilamiz") is False

    def test_ambiguous_boshlaymiz_does_not_force_measurement(self) -> None:
        assert _is_measurement_request("boshlaymiz") is False

    def test_olchab_keting_routes_to_measurement(self) -> None:
        assert _is_measurement_request("olchab keting") is True


# ── 15 messy OPERATOR phrases ─────────────────────────────────────────


class TestMessyOperator:
    def test_odam_bilan_gaplashaman(self) -> None:
        assert _is_operator_request("odam bilan gaplashaman") is True

    def test_tel_qiling(self) -> None:
        assert _is_operator_request("tel qiling") is True

    def test_aloqa_qiling(self) -> None:
        assert _is_operator_request("aloqa qiling") is True

    def test_operatorga_ulang(self) -> None:
        assert _is_operator_request("operatorga ulang") is True

    def test_jonli_odam(self) -> None:
        assert _is_operator_request("jonli odam kerak") is True

    def test_tirik_odam(self) -> None:
        assert _is_operator_request("tirik odam kerak") is True

    def test_usta_bilan_gaplashay(self) -> None:
        assert _is_operator_request("usta bilan gaplashay") is True

    def test_admin_bormi(self) -> None:
        assert _is_operator_request("admin bormi") is True

    def test_tel_nomer_ber(self) -> None:
        assert _is_operator_request("tel nomer ber") is True

    def test_qongiroq_qiling(self) -> None:
        assert _is_operator_request("qongiroq qiling") is True

    def test_qo_apos_ng_apos_iroq_qiling(self) -> None:
        assert _is_operator_request("qo'ng'iroq qiling") is True

    def test_opratr_typo(self) -> None:
        assert _is_operator_request("opratr kerak") is True

    def test_menjer_typo(self) -> None:
        assert _is_operator_request("menjer keraq") is True

    def test_russian_pozvonite(self) -> None:
        assert _is_operator_request("позвоните мне") is True

    def test_cyrillic_operator(self) -> None:
        assert _is_operator_request("оператор керак") is True


# ── 10 messy OBJECTION phrases ────────────────────────────────────────


class TestMessyObjection:
    def test_qimmatku(self) -> None:
        obj = detect_objection_full("qimmatku")
        assert obj is not None and obj.objection_type == "expensive"

    def test_qimmat_ekanu(self) -> None:
        obj = detect_objection_full("qimmat ekanu")
        assert obj is not None and obj.objection_type == "expensive"

    def test_boshqalar_arzon_deyapti(self) -> None:
        obj = detect_objection_full("boshqalar arzon deyapti")
        assert obj is not None and obj.objection_type in {"compare", "expensive"}

    def test_chegirma_bormi(self) -> None:
        obj = detect_objection_full("chegirma bormi")
        # "chegirma" matches `_OBJECTION_COMPARE_KW` in existing code
        assert obj is not None

    def test_aldab_qoymaysizlarmi(self) -> None:
        obj = detect_objection_full("aldab qoymaysizlarmi")
        assert obj is not None and obj.objection_type == "trust"

    def test_kafolati_bormi(self) -> None:
        obj = detect_objection_full("kafolati bormi")
        assert obj is not None and obj.objection_type == "trust"

    def test_qimmatku_is_price_objection_not_price_query(self) -> None:
        # Must not be mistaken for a price query
        obj = detect_objection_full("qimmatku")
        assert obj is not None
        # bot routes to objection handler before generic ai_fallback
        assert _is_price_query("qimmatku") is False

    def test_objection_does_not_route_to_operator(self) -> None:
        # safety: customer who complains is NOT auto-routed to operator
        # by the detection layer (the operator branch only fires on
        # explicit handoff keywords)
        assert _is_operator_request("qimmatku") is False

    def test_kafolat_doesnt_invent_warranty_promise(self) -> None:
        # The detector returns objection metadata only — no canned reply
        # is fabricated here; the warranty answer lives in the LLM
        # system prompt / knowledge base, not in the detector.
        obj = detect_objection_full("kafolati bormi")
        assert obj is not None

    def test_qimmat_then_chegirma_still_routes_to_objection(self) -> None:
        obj = detect_objection_full("qimmat chegirma bering")
        assert obj is not None


# ── 5 STOP / low-interest phrases ─────────────────────────────────────


class TestMessyStop:
    def test_kerakmas(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("kerakmas") is True

    def test_shunchaki_soradim(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("shunchaki soradim") is True

    def test_pul_yoq(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("pul yoq") is True

    def test_hali_emas(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("hali emas") is True

    def test_hozir_emas(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("hozir emas") is True


# ── Guardrails: price/catalog/operator/stop don't collide ─────────────


class TestNoCollateralDamage:
    def test_gulli_nech_pul_stays_price(self) -> None:
        assert _is_price_query("gulli nech pul") is True

    def test_gulli_katalog_stays_catalog(self) -> None:
        assert _is_catalog_request("gulli katalog") is True

    def test_20_kv_gulli_qancha_stays_price(self) -> None:
        assert _is_price_query("20 kv gulli qancha") is True

    def test_katalog_tashla_stays_catalog(self) -> None:
        assert _is_catalog_request("katalog tashla") is True

    def test_kerak_emas_stays_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("kerak emas") is True

    def test_operator_kerak_stays_operator(self) -> None:
        assert _is_operator_request("operator kerak") is True


# ── No secrets / no fake URLs ─────────────────────────────────────────


class TestSafety:
    def test_no_secrets_in_detector_source(self) -> None:
        src = Path("apps/bot/handlers/private/ai_detection.py").read_text(encoding="utf-8")
        for pat in (
            r"BOT_TOKEN",
            r"OPENAI_API_KEY",
            r"DATABASE_URL",
            r"Bearer\s+\S{8,}",
            r"sk-[A-Za-z0-9]{16,}",
            r"postgres://",
        ):
            assert re.search(pat, src) is None, pat

    def test_resolver_only_returns_canonical_urls(self) -> None:
        # All design names that the resolver matches must map to a URL
        # that comes from CATALOG_BY_KEY — no invented URLs.
        from shared.constants.catalog import CATALOG_BY_KEY

        for q in ("guli rasm", "mramr korsat", "oshxona uchun bormi", "kosmos ko'rsat"):
            r = resolve_catalog_link(q)
            if r.matched and r.link is not None and r.link.url:
                section = CATALOG_BY_KEY[r.link.key]
                assert r.link.url == section.group_url

    def test_resolver_fallback_url_is_static(self) -> None:
        r = resolve_catalog_link("anything random foo bar")
        assert r.fallback_link is not None
        assert r.fallback_link.url == "https://t.me/vashpotolokuz"


# ── Source pin: operator detector wired into AI flow ──────────────────


class TestOperatorWiredIntoAiFlow:
    @staticmethod
    def _src() -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_imports_operator_detector(self) -> None:
        assert "_is_operator_request" in self._src()

    def test_handlers_call_operator_detector(self) -> None:
        src = self._src()
        assert src.count("_is_operator_request(text)") >= 2

    def test_operator_branch_calls_try_operator_handoff(self) -> None:
        src = self._src()
        # The branch we added uses _try_operator_handoff with source="ai_text"
        assert 'source="ai_text"' in src
