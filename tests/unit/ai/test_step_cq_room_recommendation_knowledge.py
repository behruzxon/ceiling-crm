"""Tests for Step CQ — Room Recommendation Knowledge."""
from __future__ import annotations

from pathlib import Path


def _uz() -> str:
    return Path("shared/knowledge/uz.md").read_text(encoding="utf-8")


class TestRoomSection:
    def test_section_exists(self):
        assert "Xona bo'yicha potolok tavsiyalari" in _uz()


class TestOshxona:
    def test_exists(self):
        assert "Oshxona" in _uz()

    def test_moisture(self):
        c = _uz().lower()
        assert "namlik" in c

    def test_cleaning(self):
        c = _uz().lower()
        assert "tozalash" in c


class TestZal:
    def test_exists(self):
        c = _uz()
        assert "Zal" in c or "Mehmonxona" in c

    def test_decorative(self):
        c = _uz().lower()
        assert "gulli" in c or "mramor" in c


class TestYotoqxona:
    def test_exists(self):
        assert "Yotoqxona" in _uz()

    def test_calm(self):
        c = _uz().lower()
        assert "sokin" in c or "yumshoq" in c


class TestBolalarXonasi:
    def test_exists(self):
        assert "Bolalar" in _uz()

    def test_bright_but_safe(self):
        c = _uz().lower()
        assert "yorqin" in c


class TestKoridor:
    def test_exists(self):
        assert "Koridor" in _uz()

    def test_simple(self):
        c = _uz().lower()
        assert "oddiy" in c or "matoviy" in c


class TestHammom:
    def test_exists(self):
        assert "Hammom" in _uz()

    def test_moisture_resistant(self):
        c = _uz().lower()
        assert "namlik" in c


class TestSafety:
    def test_no_fake_media(self):
        c = _uz()
        section_start = c.find("Xona bo'yicha")
        section = c[section_start:section_start + 800] if section_start >= 0 else ""
        assert "rasm yuboram" not in section.lower()

    def test_no_guarantee_availability(self):
        c = _uz()
        assert "kafolatlamaslik" in c.lower() or "mos variant" in c.lower()

    def test_no_final_price(self):
        c = _uz()
        section_start = c.find("Xona bo'yicha")
        section = c[section_start:section_start + 800] if section_start >= 0 else ""
        assert "aniq narx" not in section.lower()

    def test_no_token(self):
        c = _uz()
        assert "sk-proj-" not in c

    def test_no_eng_arzon_in_room_section(self):
        c = _uz()
        start = c.find("Xona bo'yicha potolok tavsiyalari")
        end = c.find("## E'tirozlarga javob")
        section = c[start:end] if start >= 0 and end > start else ""
        assert "eng arzon" not in section.lower()


class TestDocExists:
    def test_doc_107(self):
        assert Path(
            "docs/AI_AGENT_SYSTEM/107_AGENT_DECISION_FIXES_CQ.md",
        ).exists()
