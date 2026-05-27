"""Integration tests for operator assignment flow — Step 8."""

from __future__ import annotations

from pathlib import Path


class TestAPIRouteModule:
    def test_module_imports(self) -> None:
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "take_handoff")
        assert hasattr(mod, "unassign_handoff")
        assert hasattr(mod, "operator_workload_summary")

    def test_assign_preserved(self) -> None:
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "assign_handoff")

    def test_contacted_preserved(self) -> None:
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "mark_contacted")

    def test_resolve_preserved(self) -> None:
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "resolve_handoff")

    def test_cancel_preserved(self) -> None:
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "cancel_handoff")


class TestServiceModule:
    def test_valid_statuses_complete(self) -> None:
        from core.services.crm_operator_handoff_service import VALID_STATUSES

        required = {"open", "waiting_phone", "assigned", "contacted", "resolved", "cancelled"}
        assert required.issubset(VALID_STATUSES)

    def test_queue_summary_has_assigned(self) -> None:
        from core.services.crm_operator_handoff_service import QueueSummary

        s = QueueSummary(total_assigned=5)
        assert s.total_assigned == 5


class TestWebTemplateShell:
    def test_template_exists(self) -> None:
        assert Path("apps/web/templates/crm_handoffs.html").exists()

    def test_renders_queue_table(self) -> None:
        content = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "vp-table" in content

    def test_has_take_action(self) -> None:
        content = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "take" in content

    def test_has_unassign_action(self) -> None:
        content = Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")
        assert "unassign" in content


class TestNoExternalCalls:
    def test_no_telegram_send(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "send_message" not in src
        assert "Bot(" not in src

    def test_no_openai_call(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "import openai" not in src
        assert "ChatCompletion" not in src

    def test_no_token_in_source(self) -> None:
        src = Path("apps/api/routes/admin_crm_handoffs.py").read_text(encoding="utf-8")
        assert "BOT_TOKEN" not in src
        assert "get_secret_value" not in src


class TestModelCompatibility:
    def test_model_has_assigned_to(self) -> None:
        from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel

        assert hasattr(CRMOperatorHandoffModel, "assigned_to_admin_id")

    def test_model_has_assigned_at(self) -> None:
        from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel

        assert hasattr(CRMOperatorHandoffModel, "assigned_at")

    def test_model_has_status(self) -> None:
        from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel

        assert hasattr(CRMOperatorHandoffModel, "status")
