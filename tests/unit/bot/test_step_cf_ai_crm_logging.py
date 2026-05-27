"""Tests for Step CF — AI CRM Logging Integration."""
from __future__ import annotations


class TestCRMServiceImports:
    def test_lead_notification_service(self):
        from core.services.lead_notification_service import (
            LeadNotificationService,
        )
        assert LeadNotificationService is not None

    def test_update_ai_scoring_importable(self):
        from apps.bot.handlers.private.ai_notifications import (
            _update_lead_ai_scoring,
        )
        assert callable(_update_lead_ai_scoring)

    def test_notify_phone_importable(self):
        from apps.bot.handlers.private.ai_notifications import (
            _notify_phone_captured,
        )
        assert callable(_notify_phone_captured)

    def test_notify_lead_importable(self):
        from apps.bot.handlers.private.ai_notifications import (
            _notify_ai_lead_collected,
        )
        assert callable(_notify_ai_lead_collected)

    def test_notify_warm_importable(self):
        from apps.bot.handlers.private.ai_notifications import (
            _notify_warm_interest,
        )
        assert callable(_notify_warm_interest)


class TestLeadScoringPersistence:
    def test_classify_score_hot(self):
        from apps.bot.handlers.private.ai_scoring import classify_score
        assert classify_score(65) == "hot"

    def test_classify_score_warm(self):
        from apps.bot.handlers.private.ai_scoring import classify_score
        assert classify_score(35) == "warm"

    def test_classify_score_cold(self):
        from apps.bot.handlers.private.ai_scoring import classify_score
        assert classify_score(10) == "cold"


class TestLeadRepoMethods:
    def test_update_ai_scoring_method(self):
        from core.repositories.lead_repo import AbstractLeadRepository
        assert hasattr(AbstractLeadRepository, "update_ai_scoring")

    def test_update_lead_status_method(self):
        from core.repositories.lead_repo import AbstractLeadRepository
        assert hasattr(AbstractLeadRepository, "update_lead_status")

    def test_update_last_action_method(self):
        from core.repositories.lead_repo import AbstractLeadRepository
        assert hasattr(AbstractLeadRepository, "update_last_action")


class TestConversationPersistence:
    def test_persist_exchange_importable(self):
        from apps.bot.handlers.private.ai_openai import _persist_exchange
        assert callable(_persist_exchange)

    def test_load_context_importable(self):
        from apps.bot.handlers.private.ai_openai import _load_context
        assert callable(_load_context)

    def test_clear_conversation_importable(self):
        from apps.bot.handlers.private.ai_openai import (
            clear_ai_conversation,
        )
        assert callable(clear_ai_conversation)

    def test_store_user_only_importable(self):
        from apps.bot.handlers.private.ai_openai import (
            _store_user_message_only,
        )
        assert callable(_store_user_message_only)


class TestMemoryPersistence:
    def test_load_memory_importable(self):
        from apps.bot.handlers.private.ai_memory import _load_ai_memory
        assert callable(_load_ai_memory)

    def test_save_memory_importable(self):
        from apps.bot.handlers.private.ai_memory import _save_ai_memory
        assert callable(_save_ai_memory)

    def test_update_from_interaction_importable(self):
        from apps.bot.handlers.private.ai_memory import (
            _update_ai_memory_from_interaction,
        )
        assert callable(_update_ai_memory_from_interaction)

    def test_greeting_builder_importable(self):
        from apps.bot.handlers.private.ai_memory import (
            _build_greeting_from_memory,
        )
        assert callable(_build_greeting_from_memory)


class TestGreetingFromMemory:
    def test_greeting_with_name(self):
        from apps.bot.handlers.private.ai_memory import (
            _build_greeting_from_memory,
        )
        mem = {"name": "Botir"}
        greeting = _build_greeting_from_memory(mem)
        assert "Botir" in greeting

    def test_greeting_empty_memory(self):
        from apps.bot.handlers.private.ai_memory import (
            _build_greeting_from_memory,
        )
        greeting = _build_greeting_from_memory({})
        assert len(greeting) > 0
