"""Tests for Step CF — AI Objection Detection & Sales Closer."""
from __future__ import annotations

from apps.bot.handlers.private.ai_scoring import (
    _OBJECTION_REPLIES,
    _OBJECTION_SCORE_DELTAS,
    ObjectionDetection,
    _build_objection_reply,
    detect_objection,
    detect_objection_full,
)


class TestObjectionDetection:
    def test_expensive_latin(self):
        assert detect_objection("qimmat ekan") == "expensive"

    def test_expensive_russian(self):
        assert detect_objection("дорого") == "expensive"

    def test_expensive_cyrillic_uz(self):
        assert detect_objection("қиммат") == "expensive"

    def test_trust(self):
        assert detect_objection("ishonch bormi") == "trust"

    def test_trust_kafolat(self):
        assert detect_objection("kafolat bormi") == "trust"

    def test_compare(self):
        assert detect_objection("boshqada arzon") == "compare"

    def test_compare_skidka(self):
        assert detect_objection("skidka bormi") == "compare"

    def test_delay(self):
        assert detect_objection("keyinroq") == "delay"

    def test_delay_oylash(self):
        assert detect_objection("o'ylab ko'raman") == "delay"

    def test_angry(self):
        assert detect_objection("kerakmas") == "angry"

    def test_no_objection(self):
        assert detect_objection("salom") is None

    def test_no_objection_area(self):
        assert detect_objection("20 m2 xona") is None


class TestObjectionFull:
    def test_returns_dataclass(self):
        result = detect_objection_full("qimmat ekan")
        assert isinstance(result, ObjectionDetection)
        assert result.objection_type == "expensive"

    def test_severity_low(self):
        result = detect_objection_full("qimmat")
        assert result is not None
        assert result.severity == "low"

    def test_severity_high(self):
        result = detect_objection_full("juda qimmat, umuman olmayman")
        assert result is not None
        assert result.severity == "high"

    def test_severity_medium(self):
        result = detect_objection_full("juda qimmatku")
        assert result is not None
        assert result.severity in ("medium", "high")

    def test_none_for_neutral(self):
        assert detect_objection_full("yaxshi") is None


class TestFuzzyObjection:
    def test_fuzzy_qimmatda(self):
        result = detect_objection_full("qimmatda bu")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_fuzzy_pulim_yetmaydi(self):
        result = detect_objection_full("pulim yetmaydi")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_fuzzy_oylash(self):
        result = detect_objection_full("o'ylab ko'raman")
        assert result is not None
        assert result.objection_type == "delay"

    def test_fuzzy_kafolat_bor(self):
        result = detect_objection_full("kafolat bormi?")
        assert result is not None
        assert result.objection_type == "trust"


class TestObjectionReply:
    def test_expensive_reply(self):
        reply = _build_objection_reply("expensive")
        assert "kafolat" in reply.lower() or "narx" in reply.lower()

    def test_trust_reply(self):
        reply = _build_objection_reply("trust")
        assert "kafolat" in reply.lower() or "rasmiy" in reply.lower()

    def test_delay_reply(self):
        reply = _build_objection_reply("delay")
        assert "mayli" in reply.lower() or "shoshil" in reply.lower()

    def test_personalized_reply(self):
        reply = _build_objection_reply("expensive", name="Botir")
        assert reply.startswith("Botir")

    def test_unknown_type_empty(self):
        reply = _build_objection_reply("nonexistent")
        assert reply == ""


class TestScoreDeltas:
    def test_expensive_positive(self):
        assert _OBJECTION_SCORE_DELTAS["expensive"] > 0

    def test_delay_negative(self):
        assert _OBJECTION_SCORE_DELTAS["delay"] < 0

    def test_angry_negative(self):
        assert _OBJECTION_SCORE_DELTAS["angry"] < 0

    def test_all_types_defined(self):
        for t in ("expensive", "trust", "compare", "delay", "angry"):
            assert t in _OBJECTION_SCORE_DELTAS

    def test_all_replies_defined(self):
        for t in ("expensive", "trust", "compare", "delay", "angry"):
            assert t in _OBJECTION_REPLIES
            assert len(_OBJECTION_REPLIES[t]) > 20


class TestSalesCloser:
    def test_imports(self):
        from apps.bot.handlers.private.sales_closer import (
            attempt_close,
            pick_closing_action,
            should_attempt_close,
        )
        assert callable(should_attempt_close)
        assert callable(pick_closing_action)
        assert callable(attempt_close)

    def test_should_attempt_high_score(self):
        from apps.bot.handlers.private.sales_closer import (
            should_attempt_close,
        )
        result = should_attempt_close(
            score=50, intent="other", memory={}, closing_confidence=None,
        )
        assert result is True

    def test_should_attempt_price_intent(self):
        from apps.bot.handlers.private.sales_closer import (
            should_attempt_close,
        )
        result = should_attempt_close(
            score=10, intent="price", memory={}, closing_confidence=None,
        )
        assert result is True

    def test_should_not_attempt_low(self):
        from apps.bot.handlers.private.sales_closer import (
            should_attempt_close,
        )
        result = should_attempt_close(
            score=5, intent="other", memory={}, closing_confidence=None,
        )
        assert result is False
