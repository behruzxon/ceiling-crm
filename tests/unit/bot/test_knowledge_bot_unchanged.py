"""Regression pins: bot behaviour is unchanged while DB knowledge lookup is OFF.

Knowledge Base CRUD (doc 156) added the admin store; gated retrieval (doc 157)
added an OPTIONAL bot lookup that is **default OFF**. These tests pin that:
* the lookup is flag-gated (`AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED`, default False);
* with the flag off the bot does not query DB knowledge (helper returns early);
* the file-based knowledge / system prompt is still loaded and used;
* the knowledge service never sends Telegram, calls OpenAI, or mutates the prompt.
"""

from __future__ import annotations

from pathlib import Path


def _ai_support() -> str:
    return Path("apps/bot/handlers/private/ai_support.py").read_text(encoding="utf-8")


def _system_prompt() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


def _settings() -> str:
    return Path("shared/config/settings.py").read_text(encoding="utf-8")


class TestLookupIsGatedAndDefaultOff:
    def test_flag_exists(self):
        assert "AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED" in _settings()

    def test_flag_defaults_off(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings().agent_knowledge_db_lookup_enabled is False

    def test_helper_checks_flag_first(self):
        # The helper reads the flag and returns before any DB work when off.
        s = _ai_support()
        idx = s.index("async def _maybe_answer_from_knowledge")
        body = s[idx : idx + 1200]
        assert "agent_knowledge_db_lookup_enabled" in body
        assert "return False" in body

    def test_helper_never_raises(self):
        s = _ai_support()
        idx = s.index("async def _maybe_answer_from_knowledge")
        body = s[idx : idx + 2400]
        assert "try:" in body and "except Exception" in body


class TestFileKnowledgeStillUsed:
    def test_system_prompt_still_reads_md_file(self):
        s = _system_prompt()
        assert "_KB_PATH" in s
        assert "read_text" in s

    def test_system_prompt_does_not_read_db(self):
        s = _system_prompt()
        assert "AgentKnowledgeItemModel" not in s
        assert "agent_knowledge_items" not in s


class TestServiceIsSafe:
    def test_service_has_no_telegram_send(self):
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "send_message" not in s

    def test_service_makes_no_openai_call(self):
        # "openai" legitimately appears in the secret-detection regex / notes;
        # assert there is no actual model call / client import / embedding API.
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "import openai" not in s
        assert "AsyncOpenAI" not in s
        assert "_call_ai" not in s
        assert ".embeddings" not in s.lower()

    def test_service_does_not_touch_system_prompt(self):
        s = Path("core/services/agent_knowledge_service.py").read_text(encoding="utf-8")
        assert "system_prompt" not in s
        assert "uz.md" not in s
