"""Step 12 — Standalone /crm/operator-digest route tests."""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATE = (
    Path(__file__).resolve().parents[3] / "apps" / "web" / "templates" / "crm_operator_digest.html"
)


@pytest.fixture(scope="module")
def src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def main_src() -> str:
    return (Path(__file__).resolve().parents[3] / "apps" / "web" / "main.py").read_text(
        encoding="utf-8"
    )


class TestRouteExists:
    def test_template_file_exists(self) -> None:
        assert TEMPLATE.exists()

    def test_route_decorator_present(self, main_src: str) -> None:
        assert '@app.get("/crm/operator-digest"' in main_src

    def test_route_handler_function(self, main_src: str) -> None:
        assert "async def crm_operator_digest" in main_src

    def test_route_renders_template(self, main_src: str) -> None:
        assert '"crm_operator_digest.html"' in main_src


class TestTemplateShell:
    def test_extends_base(self, src: str) -> None:
        assert '{% extends "base.html" %}' in src

    def test_title_block(self, src: str) -> None:
        assert "Operator Digest" in src

    def test_page_title_block(self, src: str) -> None:
        assert "Daily Operator Digest" in src


class TestKPICards:
    def test_kpi_total_open(self, src: str) -> None:
        assert 'id="kpiTotalOpen"' in src

    def test_kpi_waiting_phone(self, src: str) -> None:
        assert 'id="kpiWaitingPhone"' in src

    def test_kpi_urgent(self, src: str) -> None:
        assert 'id="kpiUrgent"' in src

    def test_kpi_high(self, src: str) -> None:
        assert 'id="kpiHigh"' in src

    def test_kpi_expired(self, src: str) -> None:
        assert 'id="kpiExpired"' in src

    def test_kpi_grid_class(self, src: str) -> None:
        assert "vp-kpi-grid" in src


class TestRecommendationsSection:
    def test_recommendations_card_present(self, src: str) -> None:
        assert "Tavsiyalar" in src

    def test_recs_list_id(self, src: str) -> None:
        assert 'id="digestRecsList"' in src


class TestPreviewSection:
    def test_text_preview_id(self, src: str) -> None:
        assert 'id="digestTextPreview"' in src

    def test_metrics_grid_id(self, src: str) -> None:
        assert 'id="digestMetricsGrid"' in src

    def test_severity_badge_id(self, src: str) -> None:
        assert 'id="digestSeverityBadge"' in src


class TestSafetyAndSends:
    def test_send_button_disabled(self, src: str) -> None:
        import re

        assert re.search(r"<button[^>]*digest-send-btn[^>]*\bdisabled\b", src) is not None

    def test_send_label_disabled(self, src: str) -> None:
        assert "Yuborish (disabled)" in src

    def test_no_active_send_endpoint(self, src: str) -> None:
        assert "operator-digest/send" not in src
        assert "/send-digest" not in src

    def test_no_aiogram_in_template(self, src: str) -> None:
        assert "aiogram" not in src

    def test_no_openai_in_template(self, src: str) -> None:
        assert "openai" not in src.lower()


class TestNoLeaks:
    def test_no_token_format(self, src: str) -> None:
        import re

        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", src)

    def test_no_bearer(self, src: str) -> None:
        assert "Bearer " not in src

    def test_no_session_hash(self, src: str) -> None:
        import re

        assert not re.search(r"\b[a-f0-9]{40,}\b", src)

    def test_no_db_url(self, src: str) -> None:
        assert "postgresql://" not in src
        assert "postgresql+asyncpg://" not in src


class TestLoaderScript:
    def test_loader_function(self, src: str) -> None:
        assert "loadOperatorDigestStandalone" in src

    def test_fetches_daily_endpoint(self, src: str) -> None:
        assert "/api/v1/admin/crm/operator-digest/daily" in src

    def test_fetches_preview_endpoint(self, src: str) -> None:
        assert "/api/v1/admin/crm/operator-digest/preview" in src

    def test_loader_runs_on_dom_load(self, src: str) -> None:
        assert "DOMContentLoaded" in src

    def test_refresh_button_present(self, src: str) -> None:
        assert "digest-refresh-btn" in src

    def test_back_link_to_handoffs(self, src: str) -> None:
        assert 'href="/crm/handoffs"' in src
