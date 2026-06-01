"""Regression pins: Knowledge Base CRUD must NOT change bot behaviour (Option A).

This sprint builds the admin-editable knowledge store + promote workflow only.
The bot does not read DB knowledge yet — these tests prove no DB-knowledge lookup
was wired into the live handlers and the file-based knowledge load is unchanged.
"""

from __future__ import annotations

from pathlib import Path


def _ai_support() -> str:
    return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")


def _system_prompt() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


class TestNoBotKnowledgeLookup:
    def test_handler_does_not_import_knowledge_service(self):
        assert "agent_knowledge_service" not in _ai_support()

    def test_handler_does_not_query_knowledge_model(self):
        s = _ai_support()
        assert "AgentKnowledgeItemModel" not in s
        assert "agent_knowledge_items" not in s

    def test_no_db_knowledge_lookup_helper(self):
        s = _ai_support().lower()
        assert "knowledge_db_lookup" not in s
        assert "lookup_knowledge" not in s


class TestFileKnowledgeUnchanged:
    def test_system_prompt_still_reads_md_file(self):
        s = _system_prompt()
        assert "_KB_PATH" in s
        assert "read_text" in s

    def test_system_prompt_does_not_read_db(self):
        s = _system_prompt()
        assert "AgentKnowledgeItemModel" not in s
        assert "agent_knowledge_items" not in s


class TestNoFlagAddedForLookup:
    def test_no_knowledge_db_lookup_flag(self):
        # Option A: we did NOT add AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED this sprint.
        settings = Path("shared/config/settings.py").read_text(encoding="utf-8")
        assert "knowledge_db_lookup" not in settings.lower()


class TestServiceIsAdminOnly:
    def test_service_has_no_telegram_send(self):
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "send_message" not in s

    def test_service_makes_no_openai_call(self):
        # "openai" legitimately appears in the secret-detection regex; assert
        # there is no actual model call / client import instead.
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "import openai" not in s
        assert "AsyncOpenAI" not in s
        assert "_call_ai" not in s

    def test_service_does_not_touch_system_prompt(self):
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "system_prompt" not in s
        assert "uz.md" not in s
