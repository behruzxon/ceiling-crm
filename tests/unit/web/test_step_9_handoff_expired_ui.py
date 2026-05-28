"""Step 9 — Handoff Expired UI tests.

Verifies the /crm/handoffs template surfaces the ``expired`` status as a
filter option and renders an expired badge, without removing existing
actions or adding any user-send buttons.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[3] / "apps" / "web" / "templates" / "crm_handoffs.html"


@pytest.fixture(scope="module")
def template_src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


class TestExpiredFilter:
    def test_template_exists(self) -> None:
        assert TEMPLATE.exists()

    def test_expired_filter_option_present(self, template_src: str) -> None:
        assert 'value="expired"' in template_src

    def test_expired_filter_uz_label(self, template_src: str) -> None:
        assert "Muddati o'tgan" in template_src

    def test_filter_dropdown_still_has_open(self, template_src: str) -> None:
        assert 'value="open"' in template_src

    def test_filter_dropdown_still_has_waiting_phone(self, template_src: str) -> None:
        assert 'value="waiting_phone"' in template_src

    def test_filter_dropdown_still_has_resolved(self, template_src: str) -> None:
        assert 'value="resolved"' in template_src


class TestExpiredBadge:
    def test_expired_badge_branch_present(self, template_src: str) -> None:
        assert "item.status == 'expired'" in template_src

    def test_expired_badge_class_present(self, template_src: str) -> None:
        assert "expired-badge" in template_src

    def test_expired_badge_neutral_styling(self, template_src: str) -> None:
        # Expired is neutral (not danger) — purely informational
        assert "vp-badge-neutral expired-badge" in template_src


class TestExistingActionsPreserved:
    def test_take_button_preserved(self, template_src: str) -> None:
        assert "'take'" in template_src or "/take" in template_src

    def test_assign_button_preserved(self, template_src: str) -> None:
        assert "'assign'" in template_src

    def test_contacted_button_preserved(self, template_src: str) -> None:
        assert "'contacted'" in template_src

    def test_resolve_button_preserved(self, template_src: str) -> None:
        assert "'resolve'" in template_src

    def test_unassign_button_preserved(self, template_src: str) -> None:
        assert "'unassign'" in template_src


class TestNoSendButton:
    def test_no_user_send_button(self, template_src: str) -> None:
        forbidden = [
            "Xabar yuborish",
            "Send to user",
            "Telegram yuborish",
        ]
        for tok in forbidden:
            assert tok not in template_src, f"forbidden send token found: {tok}"
        # The Step 11 digest card may carry a 'Yuborish (disabled)' button, but
        # any unqualified 'Yuborish' button must be disabled.
        import re

        for m in re.finditer(r"<button[^>]*>([^<]*Yuborish[^<]*)</button>", template_src):
            button_open_tag = template_src[: m.start() + template_src[m.start() :].index(">") + 1]
            # The opening tag for this match
            opening = m.group(0)
            assert "disabled" in opening or "(disabled)" in m.group(
                1
            ), f"send-like button without disabled: {m.group(0)[:120]}"
            _ = button_open_tag  # silence unused

    def test_no_eta_text(self, template_src: str) -> None:
        # No fake ETA promises rendered.
        forbidden = ["min ichida", "soat ichida", "ETA:", "ETA "]
        for tok in forbidden:
            assert tok not in template_src, f"forbidden eta token found: {tok}"

    def test_no_openai_in_template(self, template_src: str) -> None:
        assert "openai" not in template_src.lower()
