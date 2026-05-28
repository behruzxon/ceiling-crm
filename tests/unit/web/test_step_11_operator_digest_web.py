"""Step 11 — Operator digest web UI tests.

The digest card is added to /crm/handoffs page. Verifies card existence,
all required slots, dynamic loader script, no send button, no fake ETA,
no token/session leakage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[3] / "apps" / "web" / "templates" / "crm_handoffs.html"


@pytest.fixture(scope="module")
def src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


class TestCardExists:
    def test_template_exists(self) -> None:
        assert TEMPLATE.exists()

    def test_digest_card_id_present(self, src: str) -> None:
        assert 'id="operatorDigestCard"' in src

    def test_digest_card_title(self, src: str) -> None:
        assert "Daily Operator Digest" in src

    def test_digest_content_div(self, src: str) -> None:
        assert 'id="digestContent"' in src


class TestSeverityBadge:
    def test_severity_badge_id(self, src: str) -> None:
        assert 'id="digestSeverityBadge"' in src

    def test_severity_badge_class(self, src: str) -> None:
        assert "digest-severity" in src

    def test_severity_green_class_defined(self, src: str) -> None:
        assert "digest-severity-green" in src

    def test_severity_yellow_class_defined(self, src: str) -> None:
        assert "digest-severity-yellow" in src

    def test_severity_red_class_defined(self, src: str) -> None:
        assert "digest-severity-red" in src


class TestMetricsAndRecs:
    def test_digest_grid_class(self, src: str) -> None:
        assert "digest-grid" in src

    def test_digest_item_class(self, src: str) -> None:
        assert "digest-item" in src

    def test_digest_item_value(self, src: str) -> None:
        assert "digest-item-value" in src

    def test_digest_item_label(self, src: str) -> None:
        assert "digest-item-label" in src

    def test_digest_item_danger_class(self, src: str) -> None:
        assert "digest-item-danger" in src

    def test_digest_item_warning_class(self, src: str) -> None:
        assert "digest-item-warning" in src

    def test_digest_item_success_class(self, src: str) -> None:
        assert "digest-item-success" in src

    def test_recommendations_block(self, src: str) -> None:
        assert "digest-recs" in src

    def test_recommendations_label_text(self, src: str) -> None:
        assert "Tavsiyalar" in src


class TestLoaderScript:
    def test_load_function_defined(self, src: str) -> None:
        assert "loadOperatorDigest" in src

    def test_fetches_daily_endpoint(self, src: str) -> None:
        assert "/api/v1/admin/crm/operator-digest/daily" in src

    def test_refresh_button(self, src: str) -> None:
        assert "digest-refresh-btn" in src
        assert "Yangilash" in src

    def test_loader_handles_error(self, src: str) -> None:
        assert "catch" in src or "Xato" in src

    def test_loader_registered_on_dom_load(self, src: str) -> None:
        assert "DOMContentLoaded" in src
        assert "loadOperatorDigest" in src


class TestSendButtonDisabled:
    def test_send_button_marked_disabled(self, src: str) -> None:
        assert "digest-send-btn" in src
        # The send button must literally include `disabled` attribute
        # AND the user-visible label must say "disabled".
        import re

        # Match a <button> tag with class digest-send-btn that has disabled attribute
        assert re.search(r"<button[^>]*digest-send-btn[^>]*\bdisabled\b", src) is not None

    def test_send_button_label_says_disabled(self, src: str) -> None:
        assert "Yuborish (disabled)" in src

    def test_no_active_send_endpoint_reference(self, src: str) -> None:
        # No POST to /send anywhere in the new card section
        assert "operator-digest/send" not in src
        assert "/send-digest" not in src


class TestNoFakeETAOrLeaks:
    def test_no_fake_eta(self, src: str) -> None:
        forbidden = ["ETA:", "ETA ", "min ichida", "soat ichida"]
        for tok in forbidden:
            assert tok not in src, f"forbidden ETA token: {tok}"

    def test_no_openai_in_template(self, src: str) -> None:
        assert "openai" not in src.lower()

    def test_no_telegram_bot_token(self, src: str) -> None:
        import re

        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", src)

    def test_no_bearer_literal(self, src: str) -> None:
        assert "Bearer " not in src

    def test_no_session_hash_literal(self, src: str) -> None:
        # Session hashes are 32+ hex chars — ensure no literal embedded
        import re

        assert not re.search(r"\b[a-f0-9]{32,}\b", src)


class TestStyleSystem:
    def test_uses_vp_card(self, src: str) -> None:
        # The digest card should reuse the design-system vp-card class
        assert "vp-card" in src

    def test_uses_vp_badge(self, src: str) -> None:
        assert "vp-badge" in src

    def test_uses_vp_btn(self, src: str) -> None:
        assert "vp-btn" in src


class TestMobileResponsive:
    def test_grid_flex_wrap(self, src: str) -> None:
        # digest-grid uses flex-wrap so it stacks on small screens
        import re

        assert re.search(r"\.digest-grid[^}]*flex-wrap\s*:\s*wrap", src) is not None

    def test_existing_mobile_media_query_preserved(self, src: str) -> None:
        # The existing @media (max-width: 767px) block must still be present
        assert "max-width: 767px" in src


class TestExistingPagePreserved:
    def test_handoff_queue_table_still_rendered(self, src: str) -> None:
        # Step 2/8/9 features must still be present
        assert "handoff_actions" in src or "handoffAction" in src

    def test_kpi_grid_preserved(self, src: str) -> None:
        assert "vp-kpi-grid" in src

    def test_operator_workload_card_preserved(self, src: str) -> None:
        assert 'id="operatorWorkload"' in src
