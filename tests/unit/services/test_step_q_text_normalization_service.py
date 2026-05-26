"""Tests for Step Q — TextNormalizationService."""
from __future__ import annotations

from core.services.text_normalization_service import TextNormalizationService

svc = TextNormalizationService


class TestTransliteration:
    def test_narxi_qancha(self):
        r = svc.normalize("нархи қанча")
        assert "narxi" in r.latin
        assert "qancha" in r.latin

    def test_qimmat(self):
        r = svc.normalize("қиммат")
        assert r.latin == "qimmat"

    def test_operator_kerak(self):
        r = svc.normalize("оператор керак")
        assert "operator" in r.latin
        assert "kerak" in r.latin

    def test_kafolat_bormi(self):
        r = svc.normalize("кафолат борми")
        assert "kafolat" in r.latin
        assert "bormi" in r.latin

    def test_chegirma_bormi(self):
        r = svc.normalize("чегирма борми")
        assert "chegirma" in r.latin

    def test_buyurtma(self):
        r = svc.normalize("буюртма бермоқчиман")
        assert "buyurtma" in r.latin
        assert "bermoqchiman" in r.latin

    def test_usta(self):
        r = svc.normalize("уста")
        assert r.latin == "usta"

    def test_shoshilinch(self):
        r = svc.normalize("шошилинч")
        assert r.latin == "shoshilinch"

    def test_chahon(self):
        r = svc.normalize("чақир")
        assert "chaqir" in r.latin

    def test_mixed_case(self):
        r = svc.normalize("Нархи Қанча")
        assert "narxi" in r.latin.lower()

    def test_yo(self):
        r = svc.normalize("ёзманг")
        assert "yozmang" in r.latin


class TestApostropheNormalization:
    def test_o_apostrophe_right(self):
        r = svc.normalize("o'lchov")
        assert "o'lchov" in r.normalized

    def test_o_apostrophe_curly(self):
        r = svc.normalize("o‘lchov")
        assert "'" in r.normalized

    def test_o_apostrophe_backtick(self):
        r = svc.normalize("o`lchov")
        assert "'" in r.normalized


class TestWhitespace:
    def test_multi_space(self):
        r = svc.normalize("narxi   qancha")
        assert r.normalized == "narxi qancha"

    def test_leading_trailing(self):
        r = svc.normalize("  narx  ")
        assert r.normalized == "narx"

    def test_tabs(self):
        r = svc.normalize("narx\tqancha")
        assert r.normalized == "narx qancha"


class TestPunctuation:
    def test_trailing_question(self):
        r = svc.normalize("narxi qancha?")
        assert r.normalized == "narxi qancha"

    def test_trailing_exclamation(self):
        r = svc.normalize("kerak!")
        assert r.normalized == "kerak"

    def test_mid_sentence_preserved(self):
        r = svc.normalize("5x4 xona")
        assert "5x4" in r.normalized


class TestTokens:
    def test_basic_tokens(self):
        r = svc.normalize("narxi qancha")
        assert "narxi" in r.tokens
        assert "qancha" in r.tokens

    def test_token_count(self):
        r = svc.normalize("potolok narxi qancha")
        assert len(r.tokens) == 3


class TestNgrams:
    def test_bigrams(self):
        r = svc.normalize("potolok narxi qancha")
        assert "potolok narxi" in r.ngrams
        assert "narxi qancha" in r.ngrams


class TestTypoCorrection:
    def test_narhi(self):
        _, corr = svc.normalize_common_typos("narhi qancha")
        assert "narhi" in corr
        assert corr["narhi"] == "narxi"

    def test_qanca(self):
        _, corr = svc.normalize_common_typos("qanca boladi")
        assert "qanca" in corr

    def test_qncha(self):
        _, corr = svc.normalize_common_typos("qncha")
        assert "qncha" in corr

    def test_qmat(self):
        _, corr = svc.normalize_common_typos("qmat ekan")
        assert "qmat" in corr

    def test_opirator(self):
        _, corr = svc.normalize_common_typos("opirator kerak")
        assert "opirator" in corr

    def test_zakas(self):
        _, corr = svc.normalize_common_typos("zakas beraman")
        assert "zakas" in corr

    def test_no_correction_for_correct(self):
        _, corr = svc.normalize_common_typos("narxi qancha")
        assert len(corr) == 0


class TestScriptDetection:
    def test_latin_only(self):
        scripts = svc.detect_scripts("narxi qancha")
        assert "latin" in scripts

    def test_cyrillic_russian(self):
        scripts = svc.detect_scripts("сколько стоит")
        assert "cyrillic" in scripts

    def test_uzbek_cyrillic(self):
        scripts = svc.detect_scripts("нархи қанча")
        assert "uzbek_cyrillic" in scripts

    def test_mixed(self):
        scripts = svc.detect_scripts("narx сколько")
        assert "mixed" in scripts

    def test_mixed_uz_cyrillic_latin(self):
        scripts = svc.detect_scripts("қанча potolok")
        assert "mixed" in scripts


class TestLanguageDetection:
    def test_russian(self):
        r = svc.normalize("сколько стоит")
        assert "russian" in r.detected_languages

    def test_uzbek_cyrillic(self):
        r = svc.normalize("нархи қанча")
        assert "uzbek_cyrillic" in r.detected_languages

    def test_uzbek_latin(self):
        r = svc.normalize("narxi qancha")
        assert "uzbek_latin" in r.detected_languages


class TestFuzzyMatch:
    def test_exact_match(self):
        result = svc.contains_fuzzy("narxi qancha", ("narx", "qancha"))
        assert result is not None

    def test_one_char_typo(self):
        result = svc.contains_fuzzy("narhi qancha", ("narxi",), max_distance=1)
        assert result == "narxi"

    def test_too_far_no_match(self):
        result = svc.contains_fuzzy("nxxhi", ("narxi",), max_distance=1)
        assert result is None

    def test_short_word_no_match(self):
        result = svc.contains_fuzzy("ha ok yo", ("narx",), max_distance=1)
        assert result is None

    def test_distance_2_long_word(self):
        result = svc.contains_fuzzy("operitor kerak", ("operator",), max_distance=2)
        assert result == "operator"

    def test_distance_2_short_word_restricted(self):
        result = svc.contains_fuzzy("nxx test", ("narx",), max_distance=2)
        assert result is None


class TestFullNormalization:
    def test_cyrillic_end_to_end(self):
        r = svc.normalize("Нархи қанча?")
        assert "narxi" in r.latin
        assert "qancha" in r.latin
        assert r.normalized == "нархи қанча"

    def test_typo_end_to_end(self):
        r = svc.normalize("narhi qanca")
        assert "narxi" in r.latin
        assert "qancha" in r.latin

    def test_voice_artifact_preserved(self):
        r = svc.normalize("narx qancha boladi ekan")
        assert "narx" in r.latin
        assert "qancha" in r.latin
        assert "boladi" in r.latin  # filler preserved, not removed
