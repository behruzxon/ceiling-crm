"""Tests for Step CF — AI Agent Pipeline Integration."""

from __future__ import annotations


class TestAgentModuleImports:
    def test_run_orchestrator_importable(self):
        from apps.bot.handlers.private.ai_support_agent import (
            _run_orchestrator,
        )

        assert callable(_run_orchestrator)

    def test_process_lead_signal_importable(self):
        from apps.bot.handlers.private.ai_support_agent import (
            _process_lead_signal,
        )

        assert callable(_process_lead_signal)


class TestAgentServices:
    def test_lead_signal_service(self):
        from core.services.lead_signal_service import LeadSignalService

        assert LeadSignalService is not None

    def test_text_normalization_service(self):
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        assert TextNormalizationService is not None

    def test_decision_engine(self):
        from core.services.agent_decision_engine import evaluate

        assert callable(evaluate)

    def test_dynamic_offer_service(self):
        from core.services.dynamic_offer_service import DynamicOfferService

        assert DynamicOfferService is not None

    def test_conversation_policy(self):
        from core.services.conversation_policy_service import (
            ConversationPolicyService,
        )

        assert ConversationPolicyService is not None

    def test_orchestrator(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        assert AgentResponseOrchestrator is not None

    def test_sandbox(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )

        assert AgentExecutionSandboxService is not None


class TestNormalization:
    def test_normalize_cyrillic_input(self):
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        svc = TextNormalizationService()
        result = svc.normalize("нарх қанча")
        assert result is not None
        assert hasattr(result, "normalized") or hasattr(result, "text")

    def test_normalize_latin_input(self):
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        svc = TextNormalizationService()
        result = svc.normalize("narx qancha")
        assert result is not None


class TestLeadSignalExtraction:
    def test_extract_price_intent(self):
        from core.services.lead_signal_service import LeadSignalService

        svc = LeadSignalService()
        signals = svc.extract_signals("20 kv qancha turadi")
        assert signals is not None
        assert hasattr(signals, "intent") or isinstance(signals, dict)

    def test_extract_stop_intent(self):
        from core.services.lead_signal_service import LeadSignalService

        svc = LeadSignalService()
        signals = svc.extract_signals("kerak emas")
        assert signals is not None

    def test_extract_objection(self):
        from core.services.lead_signal_service import LeadSignalService

        svc = LeadSignalService()
        signals = svc.extract_signals("juda qimmat ekan")
        assert signals is not None


class TestAgentMemory:
    def test_agent_memory_service(self):
        from core.services.agent_memory_service import AgentMemoryService

        assert AgentMemoryService is not None

    def test_agent_memory_model(self):
        from infrastructure.database.models.agent_memory import (
            AgentMemoryModel,
        )

        assert AgentMemoryModel is not None


class TestOrchestratorConfig:
    def test_log_only_default(self):
        from shared.config.settings import BusinessSettings

        fields = BusinessSettings.model_fields
        mode_field = fields.get("agent_execution_mode")
        assert mode_field is not None
        assert mode_field.default == "log_only"

    def test_orchestrator_disabled_default(self):
        from shared.config.settings import BusinessSettings

        fields = BusinessSettings.model_fields
        orch = fields.get("agent_response_orchestrator_enabled")
        assert orch is not None
        assert orch.default is False

    def test_live_sender_disabled_default(self):
        from shared.config.settings import BusinessSettings

        fields = BusinessSettings.model_fields
        ls = fields.get("agent_execution_live_sender_enabled")
        assert ls is not None
        assert ls.default is False

    def test_auto_execute_disabled_default(self):
        from shared.config.settings import BusinessSettings

        fields = BusinessSettings.model_fields
        ae = fields.get("agent_execution_auto_execute_approved")
        assert ae is not None
        assert ae.default is False
