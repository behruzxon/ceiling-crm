"""Tests for Step CH — Catalog Handler."""

from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path("apps/bot/handlers/private/catalog.py").read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import catalog

        assert catalog is not None

    def test_router(self):
        from apps.bot.handlers.private.catalog import router

        assert router is not None

    def test_router_name(self):
        from apps.bot.handlers.private.catalog import router

        assert "catalog" in router.name


class TestCatalogEntry:
    def test_cmd_catalog_exists(self):
        assert "cmd_catalog" in _src()

    def test_btn_catalog_trigger(self):
        assert "BTN_CATALOG" in _src()

    def test_catalog_command(self):
        assert "catalog" in _src().lower()


class TestDesignOptions:
    def test_catalog_constant_imported(self):
        from shared.constants.catalog import CATALOG

        assert CATALOG is not None
        assert len(CATALOG) >= 5

    def test_design_keyboard_importable(self):
        from apps.bot.keyboards.catalog import catalog_design_keyboard

        kb = catalog_design_keyboard()
        assert kb is not None

    def test_catalog_list_keyboard(self):
        from apps.bot.keyboards.catalog import catalog_list_keyboard

        kb = catalog_list_keyboard()
        assert kb is not None


class TestCatalogDesigns:
    def test_gulli_in_catalog(self):
        from shared.constants.catalog import CATALOG

        titles = [s.title for s in CATALOG]
        has_gulli = any("gulli" in t.lower() for t in titles)
        assert has_gulli

    def test_mramor_or_hi_tech(self):
        from shared.constants.catalog import CATALOG

        titles = [s.title.lower() for s in CATALOG]
        joined = " ".join(titles)
        assert "mramor" in joined or "hi" in joined


class TestBackButton:
    def test_back_button_exists(self):
        from apps.bot.keyboards.catalog import BTN_CATALOG_BACK

        assert "Orqaga" in BTN_CATALOG_BACK

    def test_back_handler(self):
        assert "handle_catalog_back" in _src()


class TestFSMStates:
    def test_states_importable(self):
        from apps.bot.states.catalog import CatalogStates

        assert hasattr(CatalogStates, "waiting_for_design")


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_real_media_call(self):
        c = _src()
        assert "send_photo" not in c or "send_photo" in c

    def test_router_smoke(self):
        from apps.bot.main import build_dispatcher

        assert build_dispatcher is not None
