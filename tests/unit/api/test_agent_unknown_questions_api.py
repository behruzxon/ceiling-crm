"""Tests for the Unknown Questions Inbox API.

Source-assertion + smoke style (matches the repo's API test convention):
verify endpoints, filters, auth, the review write path, and — critically —
that there is no send / knowledge-mutation / OpenAI / Telegram surface here.
"""

from __future__ import annotations

from pathlib import Path

_SRC_PATH = "apps/api/routes/admin_agent_unknown_questions.py"


def _src() -> str:
    return Path(_SRC_PATH).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self) -> None:
        from apps.api.routes import admin_agent_unknown_questions

        assert admin_agent_unknown_questions is not None

    def test_router(self) -> None:
        from apps.api.routes.admin_agent_unknown_questions import router

        assert router is not None

    def test_registered_in_main(self) -> None:
        c = Path("apps/api/main.py").read_text(encoding="utf-8")
        assert "admin_agent_unknown_questions" in c

    def test_model_import(self) -> None:
        from infrastructure.database.models.agent_unknown_question import (
            AgentUnknownQuestionModel,
        )

        assert AgentUnknownQuestionModel.__tablename__ == "agent_unknown_questions"


class TestRouterPrefix:
    def test_prefix(self) -> None:
        from apps.api.routes.admin_agent_unknown_questions import router

        assert router.prefix == "/api/v1/admin/agent/unknown-questions"

    def test_routes_registered_on_app(self) -> None:
        from apps.api.main import app

        paths = [getattr(r, "path", "") for r in app.routes]
        assert "/api/v1/admin/agent/unknown-questions" in paths
        assert "/api/v1/admin/agent/unknown-questions/summary" in paths
        assert "/api/v1/admin/agent/unknown-questions/{question_id}/review" in paths


class TestEndpoints:
    def test_list_endpoint(self) -> None:
        assert "list_unknown_questions" in _src()

    def test_summary_endpoint(self) -> None:
        assert "/summary" in _src()

    def test_review_endpoint(self) -> None:
        assert "/{question_id}/review" in _src()

    def test_list_is_get(self) -> None:
        assert '@router.get("")' in _src()

    def test_summary_is_get(self) -> None:
        assert '@router.get("/summary")' in _src()

    def test_review_is_post(self) -> None:
        assert '@router.post("/{question_id}/review")' in _src()


class TestFilters:
    def test_status_filter(self) -> None:
        assert "status" in _src()

    def test_reason_filter(self) -> None:
        assert "reason" in _src()

    def test_severity_filter(self) -> None:
        assert "severity" in _src()

    def test_q_search_filter(self) -> None:
        assert "q:" in _src() and "ilike" in _src()

    def test_limit(self) -> None:
        assert "limit" in _src()

    def test_limit_max_100(self) -> None:
        assert "le=100" in _src()

    def test_offset(self) -> None:
        assert "offset" in _src()

    def test_order_by_created_desc(self) -> None:
        assert "created_at.desc()" in _src()


class TestSummaryFields:
    def test_total_new(self) -> None:
        assert "total_new" in _src()

    def test_high_severity(self) -> None:
        assert "high_severity" in _src()

    def test_today_count(self) -> None:
        assert "today_count" in _src()

    def test_top_reasons(self) -> None:
        assert "top_reasons" in _src()

    def test_bot_failure_rate_placeholder(self) -> None:
        assert "bot_failure_rate" in _src()

    def test_bot_failure_rate_is_none_placeholder(self) -> None:
        assert '"bot_failure_rate": None' in _src()


class TestReviewWrite:
    def test_sets_status(self) -> None:
        assert "row.status = new_status" in _src()

    def test_sets_admin_note(self) -> None:
        assert "admin_note" in _src()

    def test_sets_reviewed_at(self) -> None:
        assert "reviewed_at" in _src()

    def test_sets_reviewed_by(self) -> None:
        assert "reviewed_by" in _src()

    def test_validates_status(self) -> None:
        assert "invalid status" in _src()

    def test_note_truncated(self) -> None:
        assert "[:1000]" in _src()


class TestErrorHandling:
    def test_404_on_missing(self) -> None:
        assert "404" in _src()

    def test_not_found_detail(self) -> None:
        assert "not found" in _src().lower()

    def test_422_on_bad_status(self) -> None:
        assert "422" in _src()


class TestAuth:
    def test_auth_dependency(self) -> None:
        assert "require_api_token" in _src()

    def test_auth_on_router(self) -> None:
        assert "dependencies=[Depends(require_api_token)]" in _src()


class TestNoDangerousSurface:
    def test_no_telegram_send(self) -> None:
        assert "send_message" not in _src()

    def test_no_openai(self) -> None:
        assert "openai" not in _src().lower()

    def test_no_system_prompt_mutation(self) -> None:
        # The promote-to-faq endpoint creates a Knowledge Base item via the
        # knowledge service, but must never touch the bot's system prompt.
        s = _src().lower()
        assert "system_prompt" not in s

    def test_promote_to_faq_present_but_safe(self) -> None:
        # As of the Knowledge Base CRUD sprint, promote-to-faq IS present — it
        # delegates to the knowledge service (no FAQ table write inline, no send).
        s = _src()
        assert "promote_to_faq" in s
        assert "promote_unknown_question_to_faq" in s
        assert "create_faq" not in s  # no ad-hoc FAQ creation; goes through service

    def test_no_secret_literal(self) -> None:
        assert "sk-" not in _src()


class TestSafetyOfPreviewOnly:
    def test_returns_preview_field_not_raw(self) -> None:
        assert "original_text_preview" in _src()

    def test_does_not_expose_raw_text_column(self) -> None:
        # There is no raw-text column at all; only the preview is selected.
        assert "original_text_raw" not in _src()


class TestSmoke:
    def test_api_app(self) -> None:
        from apps.api.main import app

        assert app is not None


# ── v2: reason filter accepts new (text) reasons ──────────────────────────────


class TestV2ReasonFilterAcceptsNewReasons:
    def test_reason_param_is_free_text_not_enum(self) -> None:
        # The list endpoint declares reason as a length-bounded string (max_length
        # 40), NOT a fixed enum — so new reasons like unknown_price_question are
        # accepted without an API change.
        s = _src()
        assert 'reason: str = Query(default="", max_length=40)' in s

    def test_no_hardcoded_reason_allowlist(self) -> None:
        # There must be no rejection of unknown reason values in the list route.
        s = _src()
        assert "invalid reason" not in s.lower()

    def test_summary_top_reasons_group_by_reason(self) -> None:
        # Summary aggregates by the reason column, so new reasons appear in
        # top_reasons automatically.
        s = _src()
        assert "group_by(AgentUnknownQuestionModel.reason)" in s
