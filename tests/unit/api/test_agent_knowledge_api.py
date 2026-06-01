"""Tests for the Knowledge Base API (+ promote-to-FAQ on unknown-questions).

Source-assertion + smoke style (matches the repo's API test convention):
verify endpoints, filters, auth, validation handling, and that there is no
send / model / public surface here.
"""

from __future__ import annotations

from pathlib import Path

_KB = "apps/api/routes/admin_agent_knowledge.py"
_UQ = "apps/api/routes/admin_agent_unknown_questions.py"


def _kb() -> str:
    return Path(_KB).read_text(encoding="utf-8")


def _uq() -> str:
    return Path(_UQ).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.api.routes import admin_agent_knowledge

        assert admin_agent_knowledge is not None

    def test_router(self):
        from apps.api.routes.admin_agent_knowledge import router

        assert router is not None

    def test_registered_in_main(self):
        c = Path("apps/api/main.py").read_text(encoding="utf-8")
        assert "admin_agent_knowledge" in c

    def test_model_import(self):
        from infrastructure.database.models.agent_knowledge_item import (
            AgentKnowledgeItemModel,
        )

        assert AgentKnowledgeItemModel.__tablename__ == "agent_knowledge_items"


class TestRouterPrefix:
    def test_prefix(self):
        from apps.api.routes.admin_agent_knowledge import router

        assert router.prefix == "/api/v1/admin/agent/knowledge"

    def test_routes_on_app(self):
        from apps.api.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert "/api/v1/admin/agent/knowledge" in paths
        assert "/api/v1/admin/agent/knowledge/summary" in paths
        assert "/api/v1/admin/agent/knowledge/{item_id}" in paths
        assert "/api/v1/admin/agent/knowledge/{item_id}/archive" in paths

    def test_promote_route_on_app(self):
        from apps.api.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert "/api/v1/admin/agent/unknown-questions/{question_id}/promote-to-faq" in paths


class TestEndpoints:
    def test_list_get(self):
        assert '@router.get("")' in _kb()

    def test_summary_get(self):
        assert '@router.get("/summary")' in _kb()

    def test_detail_get(self):
        assert '@router.get("/{item_id}")' in _kb()

    def test_create_post(self):
        assert '@router.post("")' in _kb()

    def test_update_patch(self):
        assert '@router.patch("/{item_id}")' in _kb()

    def test_archive_post(self):
        assert '@router.post("/{item_id}/archive")' in _kb()

    def test_promote_post(self):
        assert '@router.post("/{question_id}/promote-to-faq")' in _uq()


class TestFilters:
    def test_status_filter(self):
        assert "status" in _kb()

    def test_category_filter(self):
        assert "category" in _kb()

    def test_language_filter(self):
        assert "language" in _kb()

    def test_q_search(self):
        assert "q:" in _kb()

    def test_limit(self):
        assert "limit" in _kb()

    def test_limit_max_100(self):
        assert "le=100" in _kb()

    def test_offset(self):
        assert "offset" in _kb()


class TestSummaryFields:
    def test_active(self):
        assert '"active"' in _kb()

    def test_draft(self):
        assert '"draft"' in _kb()

    def test_archived(self):
        assert '"archived"' in _kb()

    def test_categories(self):
        assert "categories" in _kb()


class TestCreateUpdateFields:
    def test_create_reads_title(self):
        assert 'body.get("title")' in _kb()

    def test_create_reads_question(self):
        assert 'body.get("question")' in _kb()

    def test_create_reads_answer(self):
        assert 'body.get("answer")' in _kb()

    def test_create_reads_category(self):
        assert '"category"' in _kb()

    def test_create_reads_status(self):
        assert '"status"' in _kb()

    def test_update_field_allowlist(self):
        # Only known fields are forwarded to the service on PATCH.
        s = _kb()
        assert "title" in s and "question" in s and "answer" in s and "priority" in s

    def test_calls_service(self):
        assert "agent_knowledge_service" in _kb()


class TestValidationHandling:
    def test_create_maps_validation_error_to_422(self):
        s = _kb()
        assert "KnowledgeValidationError" in s and "422" in s

    def test_update_maps_validation_error_to_422(self):
        assert _kb().count("KnowledgeValidationError") >= 2

    def test_404_on_missing_item(self):
        assert "404" in _kb()

    def test_not_found_detail(self):
        assert "not found" in _kb().lower()


class TestPromoteEndpoint:
    def test_promote_calls_service(self):
        assert "promote_unknown_question_to_faq" in _uq()

    def test_promote_404_on_missing(self):
        s = _uq()
        assert "LookupError" in s and "404" in s

    def test_promote_422_on_secret(self):
        assert "KnowledgeValidationError" in _uq() and "422" in _uq()

    def test_promote_default_draft(self):
        assert '"draft"' in _uq()

    def test_promote_returns_knowledge_item(self):
        assert "knowledge_item" in _uq()

    def test_promote_marks_converted_via_service(self):
        # The conversion happens in the service; the route just delegates.
        assert "promote_unknown_question_to_faq" in _uq()


class TestAuth:
    def test_kb_auth_dependency(self):
        assert "require_api_token" in _kb()

    def test_kb_auth_on_router(self):
        assert "dependencies=[Depends(require_api_token)]" in _kb()

    def test_uq_auth_dependency(self):
        assert "require_api_token" in _uq()


class TestNoDangerousSurface:
    def test_kb_no_send(self):
        assert "send_message" not in _kb()

    def test_kb_no_model_call(self):
        s = _kb().lower()
        assert "openai" not in s
        assert "_call_ai" not in _kb()

    def test_kb_no_prompt_mutation(self):
        s = _kb().lower()
        assert "system_prompt" not in s

    def test_kb_no_secret_literal(self):
        assert "sk-" not in _kb()

    def test_promote_no_send(self):
        assert "send_message" not in _uq()

    def test_promote_no_auto_reply(self):
        assert "auto_reply" not in _uq().lower()


class TestSmoke:
    def test_api_app(self):
        from apps.api.main import app

        assert app is not None
