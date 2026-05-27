"""Tests for Step CH — Handler Registration Smoke."""
from __future__ import annotations

from pathlib import Path


class TestAllModulesImport:
    def test_catalog(self):
        from apps.bot.handlers.private.catalog import router
        assert router is not None

    def test_packages(self):
        from apps.bot.handlers.private.packages import router
        assert router is not None

    def test_order(self):
        from apps.bot.handlers.private.order import router
        assert router is not None

    def test_lead_capture(self):
        from apps.bot.handlers.private.lead_capture import router
        assert router is not None

    def test_measurement_lead(self):
        from apps.bot.handlers.private.measurement_lead import router
        assert router is not None

    def test_payment(self):
        from apps.bot.handlers.private.payment import router
        assert router is not None


class TestNoCircularImport:
    def test_all_six_together(self):
        from apps.bot.handlers.private import (
            catalog,  # noqa: F401
            lead_capture,  # noqa: F401
            measurement_lead,  # noqa: F401
            order,  # noqa: F401
            packages,  # noqa: F401
            payment,  # noqa: F401
        )
        assert True

    def test_with_ai_support(self):
        from apps.bot.handlers.private import (
            ai_support,  # noqa: F401
            catalog,  # noqa: F401
            order,  # noqa: F401
        )
        assert True


class TestDispatcher:
    def test_build_dispatcher_imports(self):
        from apps.bot.main import build_dispatcher
        assert callable(build_dispatcher)

    def test_bot_commands(self):
        from apps.bot.main import BOT_COMMANDS
        assert len(BOT_COMMANDS) >= 10


class TestRouterRegistration:
    def test_all_routers_in_main(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        for name in [
            "catalog_router",
            "packages_router",
            "order_router",
            "lead_capture_router",
            "measurement_lead_router",
            "payment_router",
            "ai_support_router",
        ]:
            assert name in c, f"{name} not in main.py"


class TestScheduler:
    def test_scheduler_unaffected(self):
        import apps.scheduler.main  # noqa: F401
        assert True


class TestNoTokenLeak:
    def test_no_real_token_in_main(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "sk-proj-" not in c
        assert "sk-ant-" not in c

    def test_no_token_in_keyboards(self):
        c = Path("apps/bot/keyboards/main_menu.py").read_text(encoding="utf-8")
        assert "sk-" not in c
