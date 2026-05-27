"""Tests for Step CH — Packages Handler."""

from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path("apps/bot/handlers/private/packages.py").read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import packages

        assert packages is not None

    def test_router(self):
        from apps.bot.handlers.private.packages import router

        assert router is not None


class TestPackageEntry:
    def test_cmd_packages_exists(self):
        assert "cmd_packages" in _src()

    def test_btn_packages_trigger(self):
        assert "BTN_PACKAGES" in _src()


class TestPackageCallbacks:
    def test_detail_callback(self):
        assert "pkg:detail:" in _src()

    def test_calc_callback(self):
        assert "pkg:calc:" in _src()

    def test_order_callback(self):
        assert "pkg:order:" in _src()

    def test_operator_callback(self):
        assert "pkg:operator" in _src()

    def test_back_list_callback(self):
        assert "pkg:back_list" in _src()

    def test_back_main_callback(self):
        assert "pkg:back_main" in _src()


class TestPackageTypes:
    def test_standard_exists(self):
        assert "standard" in _src().lower()

    def test_premium_exists(self):
        assert "premium" in _src().lower()

    def test_vip_exists(self):
        assert "vip" in _src().lower()


class TestSafety:
    def test_no_eng_arzon_claim_in_reply(self):
        c = _src().lower()
        assert "eng arzon narx bizda" not in c

    def test_no_fake_promise(self):
        c = _src().lower()
        assert "bugun qilamiz" not in c

    def test_no_token(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_real_external_call(self):
        c = _src()
        assert "requests.get" not in c
        assert "httpx" not in c


class TestAdminNotify:
    def test_admin_notification_exists(self):
        assert "admin" in _src().lower()
        assert "send_message" in _src() or "notify" in _src().lower()


class TestRouterSmoke:
    def test_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "packages" in c
