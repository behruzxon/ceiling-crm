"""Step 11 — Operator digest API tests."""

from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path("apps/api/routes/admin_crm_operator_digest.py").read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self) -> None:
        from apps.api.routes import admin_crm_operator_digest

        assert admin_crm_operator_digest is not None

    def test_router(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import router

        assert router is not None

    def test_registered_in_main(self) -> None:
        c = Path("apps/api/main.py").read_text(encoding="utf-8")
        assert "admin_crm_operator_digest" in c


class TestRouterConfig:
    def test_prefix(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import router

        assert router.prefix == "/api/v1/admin/crm/operator-digest"

    def test_router_has_dependencies(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import router

        assert router.dependencies
        # Should require_api_token dep
        assert any("require_api_token" in str(d) for d in router.dependencies)

    def test_tag_set(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import router

        assert "operator-digest" in (router.tags or [])


class TestEndpoints:
    def test_daily_endpoint(self) -> None:
        assert "/daily" in _src()

    def test_preview_endpoint(self) -> None:
        assert "/preview" in _src()

    def test_daily_function(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import operator_digest_daily

        assert callable(operator_digest_daily)

    def test_preview_function(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import operator_digest_preview

        assert callable(operator_digest_preview)

    def test_routes_count(self) -> None:
        from apps.api.routes.admin_crm_operator_digest import router

        assert len(router.routes) >= 2


class TestQueryParams:
    def test_hours_query(self) -> None:
        assert "hours" in _src()

    def test_hours_default_24(self) -> None:
        assert "default=24" in _src()

    def test_hours_max(self) -> None:
        # Allow up to a week
        assert "le=168" in _src()


class TestSafety:
    def test_no_aiogram_import(self) -> None:
        assert "aiogram" not in _src()

    def test_no_openai_import(self) -> None:
        assert "openai" not in _src().lower()

    def test_no_telegram_send(self) -> None:
        assert "send_message" not in _src()

    def test_no_destructive_delete(self) -> None:
        assert ".delete(" not in _src()

    def test_uses_require_api_token(self) -> None:
        assert "require_api_token" in _src()

    def test_no_raw_phone_in_module(self) -> None:
        import re

        assert not re.search(r"\+998\d{9}", _src())

    def test_no_bearer_literal(self) -> None:
        assert "Bearer " not in _src()

    def test_no_sk_token(self) -> None:
        assert "sk-" not in _src()


class TestServiceWiring:
    def test_imports_build_digest(self) -> None:
        assert "build_digest" in _src()

    def test_imports_format_digest_text(self) -> None:
        assert "format_digest_text" in _src()

    def test_imports_handoff_model(self) -> None:
        assert "CRMOperatorHandoffModel" in _src()

    def test_serializer_present(self) -> None:
        assert "_serialize_result" in _src() or "asdict" in _src()


class TestResponseShape:
    def test_daily_returns_dict(self) -> None:
        import inspect

        from apps.api.routes.admin_crm_operator_digest import operator_digest_daily

        sig = inspect.signature(operator_digest_daily)
        ann = sig.return_annotation
        assert ann in (dict, "dict")

    def test_preview_returns_dict(self) -> None:
        import inspect

        from apps.api.routes.admin_crm_operator_digest import operator_digest_preview

        sig = inspect.signature(operator_digest_preview)
        ann = sig.return_annotation
        assert ann in (dict, "dict")

    def test_daily_handles_db_failure(self) -> None:
        # Module must catch DB exceptions during handoff load
        assert "except Exception" in _src()

    def test_preview_includes_text_field(self) -> None:
        # The preview endpoint should respond with a `text` field
        assert '"text"' in _src() or "'text'" in _src()

    def test_daily_includes_severity_field(self) -> None:
        assert '"severity"' in _src() or "'severity'" in _src()

    def test_daily_includes_generated_at(self) -> None:
        assert "generated_at" in _src()


class TestRegistration:
    def test_registered_after_other_crm_routers(self) -> None:
        main = Path("apps/api/main.py").read_text(encoding="utf-8")
        # Should be included; preferred to be after handoffs/missed/price_estimates
        assert "admin_crm_operator_digest_router" in main

    def test_settings_flag_present(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert hasattr(s.business, "crm_operator_digest_enabled")
        assert s.business.crm_operator_digest_enabled is False

    def test_delivery_flag_present(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert hasattr(s.business, "crm_operator_digest_delivery_enabled")
        assert s.business.crm_operator_digest_delivery_enabled is False

    def test_digest_hour_default_9(self) -> None:
        from shared.config import get_settings

        get_settings.cache_clear()
        s = get_settings()
        assert s.business.crm_operator_digest_hour == 9
