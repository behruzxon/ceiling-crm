"""Warranty / quality FAQ detector tests.

Customers ask trust-building questions in many forms — warranty
duration, smell, water resistance, safety for kids, durability,
cleaning. The detector + reply builder give a deterministic safe
canned reply mirrored from ``shared/knowledge/uz.md`` so the bot
doesn't depend on the LLM for these high-trust answers.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.bot.handlers.private.ai_detection import (
    _build_warranty_quality_reply,
    _classify_warranty_topic,
    _is_catalog_request,
    _is_measurement_request,
    _is_operator_request,
    _is_price_query,
    _is_warranty_quality_question,
)
from apps.bot.handlers.private.ai_scoring import detect_objection_full
from core.services.followup_scheduler_service import FollowupSchedulerService

# ── Warranty topic ─────────────────────────────────────────────────────


class TestWarrantyTopic:
    def test_kafolat_bormi(self) -> None:
        assert _is_warranty_quality_question("kafolat bormi") is True
        assert _classify_warranty_topic("kafolat bormi") == "warranty"

    def test_kafolati_bormi(self) -> None:
        assert _is_warranty_quality_question("kafolati bormi") is True

    def test_necha_yil_kafolat(self) -> None:
        assert _is_warranty_quality_question("necha yil kafolat") is True

    def test_kafalat_qanaqa(self) -> None:
        assert _is_warranty_quality_question("kafalat qanaqa") is True

    def test_kafolat_berasizlarmi(self) -> None:
        assert _is_warranty_quality_question("kafolat berasizlarmi") is True

    def test_rasmiy_kafolat(self) -> None:
        assert _is_warranty_quality_question("rasmiy kafolat bormi") is True


# ── Quality topic ──────────────────────────────────────────────────────


class TestQualityTopic:
    def test_sifat_qanaqa(self) -> None:
        assert _is_warranty_quality_question("sifat qanaqa") is True
        assert _classify_warranty_topic("sifat qanaqa") == "quality"

    def test_sifatlimi(self) -> None:
        assert _is_warranty_quality_question("sifatlimi") is True

    def test_sifati_qanday(self) -> None:
        assert _is_warranty_quality_question("sifati qanday") is True


# ── Durability ─────────────────────────────────────────────────────────


class TestDurabilityTopic:
    def test_yirtilib_ketmaydimi(self) -> None:
        assert _is_warranty_quality_question("yirtilib ketmaydimi") is True
        assert _classify_warranty_topic("yirtilib ketmaydimi") == "durability"

    def test_osilib_qolmaydimi(self) -> None:
        assert _is_warranty_quality_question("osilib qolmaydimi") is True

    def test_tushib_ketmaydi(self) -> None:
        assert _is_warranty_quality_question("tushib ketmaydi") is True

    def test_porvyotsya_ru(self) -> None:
        assert _is_warranty_quality_question("не порвётся") is True


# ── Smell ──────────────────────────────────────────────────────────────


class TestSmellTopic:
    def test_hid_chiqmaydimi(self) -> None:
        assert _is_warranty_quality_question("hid chiqmaydimi") is True
        assert _classify_warranty_topic("hid chiqmaydimi") == "smell"

    def test_hid_bor(self) -> None:
        assert _is_warranty_quality_question("hid bor") is True

    def test_zapakh_ru(self) -> None:
        assert _is_warranty_quality_question("запах есть") is True

    def test_pakhnet_ru(self) -> None:
        assert _is_warranty_quality_question("потолок пахнет") is True

    def test_hid_cyrillic(self) -> None:
        assert _is_warranty_quality_question("ҳид чиқадими") is True


# ── Health / safety ───────────────────────────────────────────────────


class TestHealthTopic:
    def test_sogliqqa_zararmi(self) -> None:
        assert _is_warranty_quality_question("sog'liqqa zararmi") is True
        assert _classify_warranty_topic("sog'liqqa zararmi") == "health"

    def test_zararli_emasmi(self) -> None:
        assert _is_warranty_quality_question("zararli emasmi") is True

    def test_ekologik(self) -> None:
        assert _is_warranty_quality_question("ekologik tozami") is True

    def test_vredno_ru(self) -> None:
        assert _is_warranty_quality_question("вредно для здоровья") is True


# ── Water / moisture ──────────────────────────────────────────────────


class TestWaterTopic:
    def test_suv_tegsa(self) -> None:
        assert _is_warranty_quality_question("suv tegsa nima bo'ladi") is True
        assert _classify_warranty_topic("suv tegsa nima bo'ladi") == "water"

    def test_namlikka_chidamlimi(self) -> None:
        assert _is_warranty_quality_question("namlikka chidamlimi") is True
        assert _classify_warranty_topic("namlikka chidamlimi") == "water"

    def test_hammomga_boladimi(self) -> None:
        assert _is_warranty_quality_question("hammomga bo'ladimi") is True

    def test_oshxonaga_boladimi(self) -> None:
        assert _is_warranty_quality_question("oshxonaga boladimi") is True

    def test_vannada(self) -> None:
        assert _is_warranty_quality_question("vannada bo'ladimi") is True

    def test_vlag_ru(self) -> None:
        assert _is_warranty_quality_question("влагостойкая ли") is True


# ── Heat ──────────────────────────────────────────────────────────────


class TestHeatTopic:
    def test_issiqda_buzilmaydimi(self) -> None:
        assert _is_warranty_quality_question("issiqda buzilmaydimi") is True
        assert _classify_warranty_topic("issiqda buzilmaydimi") == "heat"

    def test_haroratga_chidamli(self) -> None:
        assert _is_warranty_quality_question("haroratga chidamli") is True


# ── Cleaning ──────────────────────────────────────────────────────────


class TestCleanTopic:
    def test_artib_tozalasa(self) -> None:
        assert _is_warranty_quality_question("artib tozalasa bo'ladimi") is True
        assert _classify_warranty_topic("artib tozalasa bo'ladimi") == "clean"

    def test_chang_yigiladi(self) -> None:
        assert _is_warranty_quality_question("chang yig'iladimi") is True

    def test_myt_ru(self) -> None:
        assert _is_warranty_quality_question("как мыть потолок") is True


# ── Reply quality / safety ────────────────────────────────────────────


class TestReplyContent:
    def test_warranty_reply_mentions_15_yil(self) -> None:
        r = _build_warranty_quality_reply("kafolat bormi")
        assert "15 yil" in r

    def test_smell_reply_explains_1_2_days(self) -> None:
        r = _build_warranty_quality_reply("hid chiqadimi")
        assert "1–2" in r or "1-2" in r

    def test_water_reply_mentions_pvc_or_chidamli(self) -> None:
        r = _build_warranty_quality_reply("namlikka chidamlimi")
        assert "PVC" in r or "chidamli" in r

    def test_clean_reply_mentions_artish(self) -> None:
        r = _build_warranty_quality_reply("artib tozalasa bo'ladimi")
        assert "arting" in r.lower() or "artish" in r.lower()

    def test_health_reply_says_xavfsiz(self) -> None:
        r = _build_warranty_quality_reply("sog'liqqa zararmi")
        assert "xavfsiz" in r.lower()

    def test_no_fake_100_percent(self) -> None:
        for q in (
            "kafolat bormi",
            "yirtilib ketmaydimi",
            "hid chiqadimi",
            "namlikka chidamlimi",
        ):
            r = _build_warranty_quality_reply(q)
            assert "100%" not in r
            assert "100 %" not in r

    def test_no_darhol_bugun_in_any_reply(self) -> None:
        for q in (
            "kafolat bormi",
            "sifat qanaqa",
            "yirtilib ketmaydimi",
            "hid chiqadimi",
            "sog'liqqa zararmi",
            "suv tegsa",
            "issiqda buzilmaydimi",
            "tozalash mumkinmi",
        ):
            r = _build_warranty_quality_reply(q).lower()
            assert not re.search(r"\bdarhol\b", r)
            assert not re.search(r"\bhozir\b", r)
            assert not re.search(r"\bbugun\b", r)

    def test_no_secrets_in_reply(self) -> None:
        for q in ("kafolat bormi", "sifat qanaqa", "hammomga boladimi"):
            r = _build_warranty_quality_reply(q)
            for pat in (
                r"BOT_TOKEN",
                r"OPENAI",
                r"DATABASE_URL",
                r"Bearer\s+\S{4,}",
                r"sk-[A-Za-z0-9]{16,}",
                r"postgres://",
            ):
                assert re.search(pat, r) is None

    def test_replies_are_concise(self) -> None:
        # Trust replies should stay under 6 lines and 500 chars.
        for q in (
            "kafolat bormi",
            "yirtilib ketmaydimi",
            "hid chiqadimi",
            "namlikka chidamlimi",
            "artib tozalasa bo'ladimi",
        ):
            r = _build_warranty_quality_reply(q)
            assert r.count("\n") <= 6, q
            assert len(r) <= 500, q


# ── Regression: warranty doesn't swallow other intents ────────────────


class TestNoCollateralDamage:
    def test_gulli_nech_pul_stays_price(self) -> None:
        # warranty detector returns False for pure price intent
        assert _is_warranty_quality_question("gulli nech pul") is False
        assert _is_price_query("gulli nech pul") is True

    def test_gulli_katalog_stays_catalog(self) -> None:
        assert _is_warranty_quality_question("gulli katalog") is False
        assert _is_catalog_request("gulli katalog") is True

    def test_operator_kerak_stays_operator(self) -> None:
        assert _is_warranty_quality_question("operator kerak") is False
        assert _is_operator_request("operator kerak") is True

    def test_kerak_emas_stays_stop(self) -> None:
        assert _is_warranty_quality_question("kerak emas") is False
        assert FollowupSchedulerService.is_stop_signal("kerak emas") is True

    def test_kelib_olchang_stays_measurement(self) -> None:
        assert _is_warranty_quality_question("kelib o'lchang") is False
        assert _is_measurement_request("kelib o'lchang") is True

    def test_chegirma_bormi_stays_objection_not_warranty(self) -> None:
        # "chegirma" is a price-objection topic, not a warranty FAQ.
        # The warranty detector should not steal it.
        assert _is_warranty_quality_question("chegirma bormi") is False
        obj = detect_objection_full("chegirma bormi")
        assert obj is not None


# ── Wiring: warranty branch runs before objection detector ────────────


class TestRoutingOrder:
    @staticmethod
    def _src() -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_warranty_branch_present_twice(self) -> None:
        src = self._src()
        assert src.count("_is_warranty_quality_question(text)") >= 2

    def test_warranty_runs_before_objection(self) -> None:
        src = self._src()
        for handler in ("handle_ai_question", "handle_ai_message"):
            handler_start = src.index(f"def {handler}")
            # Take a generous window after the handler def
            chunk = src[handler_start : handler_start + 8000]
            war_idx = chunk.find("_is_warranty_quality_question(text)")
            obj_idx = chunk.find("detect_objection_full(text)")
            if war_idx == -1 or obj_idx == -1:
                continue
            assert war_idx < obj_idx, f"{handler}: warranty must precede objection"

    def test_imports_reply_builder(self) -> None:
        assert "_build_warranty_quality_reply" in self._src()


# ── No secret patterns in detector source ─────────────────────────────


class TestDetectorSourceSafe:
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
