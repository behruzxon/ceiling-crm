"""Regression: customer-facing copy has no exact-ETA promise and one social-proof number.

Two P2 deploy-readiness issues:
  - "24 soat ichida qayta aloqa" promised a specific callback time, violating the
    project rule (system prompt: never promise an exact time/ETA unless the
    operator confirms). Appeared in about.py, order.py, promotions.py.
  - The completed-project count diverged: about.py advertised "10 000+" while the
    knowledge base and the AI objection reply use the canonical "1000+".

Canonical copy:
  - ETA -> non-committal "imkon qadar tez bog'lanadi" (no hour count)
  - completed-object social proof -> "1000+"

Intentionally NOT changed (different metric / not an ETA):
  - packages.py "10 000+ dizayn va faktura" is a design-catalog count.
  - about.py "24/7 tezkor javob" is an availability claim, not a callback ETA.

Offline: reads handler / knowledge source — no DB/network/Telegram/OpenAI.
"""

from __future__ import annotations

from pathlib import Path

_ABOUT = Path("apps/bot/handlers/private/about.py")
_ORDER = Path("apps/bot/handlers/private/order.py")
_PROMOTIONS = Path("apps/bot/handlers/private/promotions.py")
_AI_DETECTION = Path("apps/bot/handlers/private/ai_detection.py")
_PACKAGES = Path("apps/bot/handlers/private/packages.py")
_KB_LOADED = Path("apps/bot/ai/knowledge/uz.md")
_KB_SHARED = Path("shared/knowledge/uz.md")

_ETA_HANDLERS = (_ABOUT, _ORDER, _PROMOTIONS)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── no exact callback-time promise ───────────────────────────────────────────


class TestNoExactEtaPromise:
    def test_no_24_soat_callback_promise(self):
        # "24/7" availability does not match "24 soat"; the hour-count ETA must be gone.
        for p in _ETA_HANDLERS:
            assert "24 soat" not in _read(p), f"{p}: exact-ETA '24 soat' promise remains"

    def test_no_24h_qayta_aloqa_bullet(self):
        for p in (_ABOUT, _PROMOTIONS):
            assert "24 soat ichida qayta aloqa" not in _read(p)

    def test_non_committal_wording_present(self):
        for p in _ETA_HANDLERS:
            assert "imkon qadar tez" in _read(p), f"{p}: missing operator-safe wording"


# ── one canonical social-proof number for completed objects ──────────────────


class TestSocialProofCanonical:
    def test_about_uses_1000_plus_object_count(self):
        src = _read(_ABOUT)
        assert "1000+ muvaffaqiyatli topshirilgan obyekt" in src
        assert "10 000+" not in src  # the inflated object count is gone

    def test_canonical_1000_plus_in_knowledge_and_ai(self):
        assert "1000+" in _read(_AI_DETECTION)
        assert "1000+" in _read(_KB_LOADED)
        assert "1000+" in _read(_KB_SHARED)

    def test_design_catalog_count_left_unchanged(self):
        # Different metric (design variety, not completed objects) — must NOT be touched.
        assert "10 000+ dizayn" in _read(_PACKAGES)
