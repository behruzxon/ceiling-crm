"""Tests for operator assignment UI — Step 8."""

from __future__ import annotations

from pathlib import Path

TEMPLATE_PATH = Path("apps/web/templates/crm_handoffs.html")


def _read() -> str:
    assert TEMPLATE_PATH.exists()
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestAssignmentColumn:
    def test_has_assigned_header(self) -> None:
        assert "Tayinlangan" in _read()

    def test_has_assigned_badge(self) -> None:
        assert "assigned-badge" in _read()

    def test_has_unassigned_badge(self) -> None:
        assert "unassigned-badge" in _read()

    def test_assigned_to_admin_id_shown(self) -> None:
        assert "assigned_to_admin_id" in _read()


class TestAssignmentFilter:
    def test_assigned_filter_exists(self) -> None:
        assert "assignedFilter" in _read()

    def test_unassigned_option(self) -> None:
        content = _read()
        assert "unassigned" in content.lower()
        assert "Tayinlanmagan" in content

    def test_assigned_option(self) -> None:
        content = _read()
        assert "assigned" in content

    def test_filter_applies(self) -> None:
        assert "applyFilters" in _read()


class TestOperatorWorkload:
    def test_workload_card_exists(self) -> None:
        assert "operatorWorkload" in _read()

    def test_workload_content(self) -> None:
        assert "workloadContent" in _read()

    def test_workload_title(self) -> None:
        assert "Operator yuklamasi" in _read()

    def test_load_workload_function(self) -> None:
        assert "loadWorkload" in _read()

    def test_workload_grid_css(self) -> None:
        assert ".workload-grid" in _read()

    def test_workload_item_css(self) -> None:
        assert ".workload-item" in _read()

    def test_workload_urgent_css(self) -> None:
        assert ".workload-item-urgent" in _read()

    def test_fetches_operator_summary(self) -> None:
        assert "/operators/summary" in _read()


class TestActionButtons:
    def test_take_button_exists(self) -> None:
        assert "take-btn" in _read()

    def test_take_button_text(self) -> None:
        assert "Olish" in _read()

    def test_assign_button_exists(self) -> None:
        assert "assign-btn" in _read()

    def test_unassign_button_exists(self) -> None:
        assert "unassign-btn" in _read()

    def test_unassign_button_text(self) -> None:
        assert "Chiqarish" in _read()

    def test_contacted_button_preserved(self) -> None:
        assert "contacted-btn" in _read()

    def test_contacted_text_preserved(self) -> None:
        assert "Bog'landim" in _read()

    def test_resolve_button_preserved(self) -> None:
        assert "resolve-btn" in _read()

    def test_resolve_text_preserved(self) -> None:
        assert "Hal qildim" in _read()

    def test_cancel_button_preserved(self) -> None:
        assert "cancel-btn" in _read()

    def test_cancel_text_preserved(self) -> None:
        assert "Bekor" in _read()

    def test_handoff_action_function(self) -> None:
        assert "handoffAction" in _read()


class TestActionBanner:
    def test_banner_element(self) -> None:
        assert "actionBanner" in _read()

    def test_success_banner_css(self) -> None:
        assert "action-banner-success" in _read()

    def test_error_banner_css(self) -> None:
        assert "action-banner-error" in _read()

    def test_show_banner_function(self) -> None:
        assert "showBanner" in _read()


class TestSecurity:
    def test_no_fake_eta(self) -> None:
        content = _read()
        assert " ETA " not in content and "ETA:" not in content

    def test_no_send_button(self) -> None:
        content = _read()
        assert "Yuborish" not in content or "send_message" not in content

    def test_no_token(self) -> None:
        content = _read()
        assert "sk-" not in content
        assert "BOT_TOKEN" not in content

    def test_no_session_hash(self) -> None:
        assert "session_id_hash" not in _read()

    def test_phone_masked(self) -> None:
        assert "phone_masked" in _read()


class TestKPICards:
    def test_open_kpi(self) -> None:
        assert "total_open" in _read()

    def test_waiting_phone_kpi(self) -> None:
        assert "total_waiting_phone" in _read()

    def test_assigned_kpi(self) -> None:
        assert "total_assigned" in _read()

    def test_urgent_kpi(self) -> None:
        assert "total_urgent" in _read()

    def test_high_kpi(self) -> None:
        assert "total_high" in _read()


class TestDesignSystem:
    def test_uses_vp_card(self) -> None:
        assert "vp-card" in _read()

    def test_uses_vp_badge(self) -> None:
        assert "vp-badge" in _read()

    def test_uses_vp_table(self) -> None:
        assert "vp-table" in _read()

    def test_uses_vp_btn(self) -> None:
        assert "vp-btn" in _read()


class TestResponsive:
    def test_mobile_breakpoint(self) -> None:
        assert "767px" in _read()

    def test_actions_stack_mobile(self) -> None:
        content = _read()
        assert "handoff-actions" in content
        assert "flex-direction: column" in content or "flex-wrap" in content

    def test_kontakt_link_preserved(self) -> None:
        assert "Kontakt" in _read()
