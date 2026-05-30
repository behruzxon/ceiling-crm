"""P0-1 fix: measurement / order intent priority.

Pins the broadened ``_MEASUREMENT_TRIGGERS`` set and the script-aware
Cyrillic fall-through, plus the routing-order invariant that the
caller (``ai_support.handle_ai_*``) already checks measurement
before objection detection — so messages like "ertaga kelib
o'lchang" route to the measurement flow instead of being swallowed
by the delay-objection detector.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.bot.handlers.private.ai_detection import (
    _is_catalog_request,
    _is_measurement_request,
    _is_price_query,
)
from apps.bot.handlers.private.ai_scoring import detect_objection_full
from core.services.followup_scheduler_service import FollowupSchedulerService

# ── Latin measurement phrases ──────────────────────────────────────────


class TestLatinMeasurement:
    def test_kelib_olchang_apos(self) -> None:
        assert _is_measurement_request("kelib o'lchang") is True

    def test_kelib_olchang_plain(self) -> None:
        assert _is_measurement_request("kelib olchang") is True

    def test_olchov_kerak(self) -> None:
        assert _is_measurement_request("olchov kerak") is True

    def test_olchov_kerak_apos(self) -> None:
        assert _is_measurement_request("o'lchov kerak") is True

    def test_ulchov_typo(self) -> None:
        assert _is_measurement_request("ulchov kerak") is True

    def test_ustani_chaqir(self) -> None:
        assert _is_measurement_request("ustani chaqir") is True

    def test_master_chaqir(self) -> None:
        assert _is_measurement_request("master chaqir") is True

    def test_montajchi_chaqir(self) -> None:
        assert _is_measurement_request("montajchi chaqir") is True

    def test_ustani_jonating(self) -> None:
        assert _is_measurement_request("ustani jonating") is True

    def test_ustani_yubor(self) -> None:
        assert _is_measurement_request("ustani yubor") is True

    def test_kelinglar(self) -> None:
        assert _is_measurement_request("kelinglar") is True

    def test_uyga_keling(self) -> None:
        assert _is_measurement_request("uyga keling") is True

    def test_manzilga_keling(self) -> None:
        assert _is_measurement_request("manzilga keling") is True

    def test_kelib_olchab_bering(self) -> None:
        assert _is_measurement_request("kelib olchab bering") is True

    def test_olchab_keting(self) -> None:
        assert _is_measurement_request("olchab keting") is True


# ── Measurement wins over delay when both signals appear ──────────────


class TestMeasurementBeatsDelay:
    """The caller (ai_support.handle_ai_*) checks measurement first.
    These tests pin that the detector still recognises the
    measurement intent even when a delay keyword (e.g. ``ertaga``,
    ``keyin``) is also present, so the caller's check fires."""

    def test_ertaga_kelib_olchang(self) -> None:
        assert _is_measurement_request("ertaga kelib o'lchang") is True

    def test_ertaga_ustani_chaqir(self) -> None:
        assert _is_measurement_request("ertaga ustani chaqir") is True

    def test_ertaga_olchov_qiling(self) -> None:
        assert _is_measurement_request("ertaga olchov qiling") is True

    def test_ertaga_olchovga_kelinglar(self) -> None:
        assert _is_measurement_request("ertaga olchovga kelinglar") is True

    def test_ertaga_usta_yuboring(self) -> None:
        assert _is_measurement_request("ertaga usta yuboring") is True

    def test_keyinroq_olchang(self) -> None:
        # "keyin" is delay, but "olchang" is measurement → measurement
        # still wins because the caller checks measurement first.
        assert _is_measurement_request("keyinroq olchang") is True


# ── Cyrillic measurement phrases ──────────────────────────────────────


class TestCyrillicMeasurement:
    def test_olchang_cyr(self) -> None:
        assert _is_measurement_request("ўлчанг") is True

    def test_olchov_cyr(self) -> None:
        assert _is_measurement_request("ўлчов керак") is True

    def test_kelib_olchang_cyr(self) -> None:
        assert _is_measurement_request("келиб ўлчанг") is True

    def test_kelib_ulchang_cyr(self) -> None:
        assert _is_measurement_request("келиб улчанг") is True

    def test_usta_chakir_cyr(self) -> None:
        assert _is_measurement_request("уста чақир") is True

    def test_usta_yuboring_cyr(self) -> None:
        assert _is_measurement_request("уста юборинг") is True

    def test_ertaga_kelib_olchang_cyr(self) -> None:
        assert _is_measurement_request("эртага келиб ўлчанг") is True

    def test_zamer(self) -> None:
        assert _is_measurement_request("замер") is True

    def test_zamerschik(self) -> None:
        assert _is_measurement_request("замерщик") is True

    def test_master_ru(self) -> None:
        assert _is_measurement_request("мастер пришлите") is True

    def test_zavtra_zamer(self) -> None:
        assert _is_measurement_request("завтра замер") is True

    def test_zamer_kerak_mixed(self) -> None:
        assert _is_measurement_request("замер kerak") is True


# ── Delay objection STILL fires when there's no measurement signal ────


class TestDelayObjectionPreserved:
    def test_ertaga_gaplashamiz_is_delay(self) -> None:
        assert _is_measurement_request("ertaga gaplashamiz") is False
        obj = detect_objection_full("ertaga gaplashamiz")
        assert obj is not None and obj.objection_type == "delay"

    def test_keyinroq_is_delay(self) -> None:
        assert _is_measurement_request("keyinroq") is False
        obj = detect_objection_full("keyinroq")
        assert obj is not None and obj.objection_type == "delay"

    def test_hozir_emas_is_delay(self) -> None:
        assert _is_measurement_request("hozir emas") is False
        obj = detect_objection_full("hozir emas")
        assert obj is not None and obj.objection_type == "delay"

    def test_vaqtim_yoq_is_delay(self) -> None:
        assert _is_measurement_request("vaqtim yo'q") is False
        obj = detect_objection_full("vaqtim yo'q")
        assert obj is not None and obj.objection_type == "delay"


# ── Other intents unaffected ──────────────────────────────────────────


class TestNoCollateralDamage:
    def test_operator_kerak_unaffected(self) -> None:
        # Not a measurement and not a delay objection
        assert _is_measurement_request("operator kerak") is False
        assert detect_objection_full("operator kerak") is None

    def test_gulli_nech_pul_is_price(self) -> None:
        assert _is_price_query("gulli nech pul") is True
        assert _is_measurement_request("gulli nech pul") is False

    def test_20_kv_gulli_qancha_is_price(self) -> None:
        assert _is_price_query("20 kv gulli qancha") is True
        assert _is_measurement_request("20 kv gulli qancha") is False

    def test_gulli_katalog_is_catalog(self) -> None:
        assert _is_catalog_request("gulli katalog") is True
        assert _is_measurement_request("gulli katalog") is False

    def test_kerak_emas_is_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("kerak emas") is True
        assert _is_measurement_request("kerak emas") is False


# ── Source pin: routing order in ai_support.py ────────────────────────


class TestAiSupportRoutingOrder:
    @staticmethod
    def _src() -> str:
        return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")

    def test_measurement_check_runs_before_objection(self) -> None:
        src = self._src()
        # Both handlers must call _is_measurement_request before
        # detect_objection_full so measurement wins.
        for handler_marker in ("handle_ai_question", "handle_ai_message"):
            handler_start = src.index(f"def {handler_marker}")
            handler_end = (
                src.index("\n@", handler_start + 1) if "\n@" in src[handler_start:] else len(src)
            )
            chunk = src[handler_start:handler_end]
            meas = chunk.find("_is_measurement_request(text)")
            objc = chunk.find("detect_objection_full(text)")
            if meas == -1 or objc == -1:
                continue
            assert meas < objc, f"{handler_marker}: measurement check must precede objection"

    def test_trigger_set_contains_new_phrases(self) -> None:
        src = Path("apps/bot/handlers/private/ai_detection.py").read_text(encoding="utf-8")
        for phrase in (
            "kelib o'lchang",
            "ustani chaqir",
            "kelinglar",
            "manzilga keling",
            "ўлчанг",
            "келиб ўлчанг",
            "уста чақир",
            "замер",
            "мастер",
        ):
            assert phrase in src, f"missing trigger: {phrase!r}"


# ── No secret patterns inside detector source ─────────────────────────


class TestDetectorSourceNoSecrets:
    def test_no_secrets_in_detector(self) -> None:
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
