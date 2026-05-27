"""Tests for Step CQ — Objection Phrase Fix."""
from __future__ import annotations

from apps.bot.handlers.private.ai_scoring import (
    _OBJECTION_REPLIES,
    detect_objection,
    detect_objection_full,
)


class TestNewComparePhrases:
    def test_boshqalar_arzon(self):
        assert detect_objection("boshqalar arzon") == "compare"

    def test_boshqa_joyda_arzon(self):
        assert detect_objection("boshqa joyda arzon") == "compare"

    def test_boshqa_ustalar_arzon(self):
        assert detect_objection("boshqa ustalar arzon dedi") == "compare"

    def test_raqobatchilar_arzon(self):
        assert detect_objection("raqobatchilar arzon") == "compare"

    def test_ular_arzonroq(self):
        assert detect_objection("ular arzonroq qilyapti") == "compare"

    def test_boshqasi_arzon(self):
        assert detect_objection("boshqasi arzon") == "compare"

    def test_russian_drugie(self):
        assert detect_objection("другие дешевле") == "compare"

    def test_cyrillic_boshqalar(self):
        assert detect_objection("бошқалар арзон") == "compare"


class TestExistingCompareStillWorks:
    def test_boshqada_arzon(self):
        assert detect_objection("boshqada arzon") == "compare"

    def test_arzonroq(self):
        assert detect_objection("arzonroq") == "compare"

    def test_skidka(self):
        assert detect_objection("skidka bormi") == "compare"

    def test_deshevle(self):
        assert detect_objection("дешевле") == "compare"


class TestReplyNoEngArzon:
    def test_compare_reply_no_eng_arzon(self):
        reply = _OBJECTION_REPLIES["compare"]
        assert "eng arzon" not in reply.lower()

    def test_compare_reply_no_discount(self):
        reply = _OBJECTION_REPLIES["compare"]
        assert "chegirma qilib beraman" not in reply.lower()

    def test_compare_reply_has_value(self):
        reply = _OBJECTION_REPLIES["compare"]
        assert "kafolat" in reply.lower() or "sifat" in reply.lower()


class TestSeverity:
    def test_boshqalar_severity(self):
        r = detect_objection_full("boshqalar arzon")
        assert r is not None
        assert r.severity in ("low", "medium", "high")

    def test_normal_text_safe(self):
        assert detect_objection("salom") is None

    def test_price_query_not_objection(self):
        assert detect_objection("20 kv narx") is None


class TestSmoke:
    def test_bot_imports(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_dispatcher(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None
