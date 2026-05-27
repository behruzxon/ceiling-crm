"""Tests for Step CF — AI Button Entry Flow."""
from __future__ import annotations

from pathlib import Path


def _src(name: str) -> str:
    return Path(f"apps/bot/handlers/private/{name}").read_text(encoding="utf-8")


class TestButtonDefinition:
    def test_btn_ai_text_exists(self):
        c = Path("apps/bot/keyboards/main_menu.py").read_text(encoding="utf-8")
        assert "AI yordam" in c

    def test_btn_ai_constant(self):
        from apps.bot.keyboards.main_menu import BTN_AI
        assert "AI" in BTN_AI

    def test_deep_link_ai_in_group_keyboard(self):
        c = Path("apps/bot/keyboards/main_menu.py").read_text(encoding="utf-8")
        assert '"ai"' in c and "_url" in c


class TestEntryHandler:
    def test_cmd_ai_start_exists(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_start
        assert callable(cmd_ai_start)

    def test_handler_matches_btn_ai(self):
        c = _src("ai_support.py")
        assert "BTN_AI" in c or "AI yordam" in c

    def test_deep_link_routes_to_ai(self):
        c = Path("apps/bot/handlers/private/support.py").read_text(
            encoding="utf-8",
        )
        assert '"ai"' in c
        assert "cmd_ai_start" in c


class TestFSMStates:
    def test_states_importable(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert AiSupportStates is not None

    def test_waiting_for_name(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert hasattr(AiSupportStates, "waiting_for_name")

    def test_waiting_for_question(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert hasattr(AiSupportStates, "waiting_for_ai_question")

    def test_waiting_for_district(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert hasattr(AiSupportStates, "waiting_for_district")

    def test_waiting_for_phone(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert hasattr(AiSupportStates, "waiting_for_phone")

    def test_waiting_photo(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        assert hasattr(AiSupportStates, "waiting_photo")

    def test_seven_states_total(self):
        from apps.bot.handlers.private.ai_states import AiSupportStates
        states = [
            s for s in dir(AiSupportStates)
            if not s.startswith("_")
            and s not in ("model_config", "model_fields")
        ]
        assert len(states) >= 7


class TestRouterRegistration:
    def test_router_in_dispatcher(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "ai_support_router" in c

    def test_router_importable(self):
        from apps.bot.handlers.private.ai_support import router
        assert router is not None

    def test_no_duplicate_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        count = c.count("ai_support_router")
        assert 2 <= count <= 4  # import + include (+ possible alias)


class TestFailsafeUI:
    def test_failsafe_text_exists(self):
        from apps.bot.handlers.private.ai_states import _FAILSAFE_TEXT
        assert "texnik nosozlik" in _FAILSAFE_TEXT

    def test_failsafe_kb_exists(self):
        from apps.bot.handlers.private.ai_states import _FAILSAFE_KB
        assert _FAILSAFE_KB is not None

    def test_ai_keyboard_exists(self):
        from apps.bot.handlers.private.ai_states import _ai_keyboard
        kb = _ai_keyboard()
        assert kb is not None
