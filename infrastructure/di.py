"""
Dependency injection wiring.

Provides factory functions that construct service objects with their
repository dependencies. No heavy DI framework — aiogram's handler
data dict serves as the container.

Usage in middleware:
    session = get_session()
    data["user_service"] = get_user_service(session)

Usage in handlers:
    async def handler(message, user_service: UserService, **data):
        user = await user_service.get_or_create(...)
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.events.bus import event_bus
from core.services.admin_group_service import AdminGroupService
from core.services.broadcast_service import BroadcastService
from core.services.crm_service import CRMService
from core.services.group_settings_service import GroupSettingsService
from core.services.lead_service import LeadService
from core.services.payment_service import PaymentService
from core.services.pipeline_service import PipelineService
from core.services.user_service import UserService
from core.services.warranty_service import WarrantyService
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.audit_log_repo import PostgresAuditLogRepository
from infrastructure.database.repositories.blocked_chat_repo import PostgresBlockedChatRepository
from infrastructure.database.repositories.broadcast_repo import PostgresBroadcastRepository
from infrastructure.database.repositories.group_settings_repo import PostgresGroupSettingsRepository
from infrastructure.database.repositories.lead_action_repo import PostgresLeadActionRepository
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.repositories.payment_repo import PostgresPaymentRepository
from infrastructure.database.repositories.pipeline_repo import PostgresPipelineRepository
from infrastructure.database.repositories.user_repo import PostgresUserRepository
from infrastructure.database.repositories.warranty_repo import PostgresWarrantyRepository


def get_user_repo(session: AsyncSession) -> PostgresUserRepository:
    return PostgresUserRepository(session)


def get_lead_repo(session: AsyncSession) -> PostgresLeadRepository:
    return PostgresLeadRepository(session)


def get_pipeline_repo(session: AsyncSession) -> PostgresPipelineRepository:
    return PostgresPipelineRepository(session)


def get_user_service(session: AsyncSession) -> UserService:
    return UserService(get_user_repo(session))


def get_lead_service(session: AsyncSession) -> LeadService:
    return LeadService(
        lead_repo=get_lead_repo(session),
        pipeline_repo=get_pipeline_repo(session),
        event_bus=event_bus,
        action_repo=PostgresLeadActionRepository(session),
    )


def get_group_settings_service(session: AsyncSession) -> GroupSettingsService:
    return GroupSettingsService(PostgresGroupSettingsRepository(session))


def get_payment_service(session: AsyncSession) -> PaymentService:
    return PaymentService(PostgresPaymentRepository(session))


def get_warranty_service(session: AsyncSession) -> WarrantyService:
    return WarrantyService(PostgresWarrantyRepository(session))


def get_crm_service(session: AsyncSession) -> CRMService:
    return CRMService(
        lead_repo=get_lead_repo(session),
        pipeline_repo=get_pipeline_repo(session),
        event_bus=event_bus,
    )


def get_admin_group_service(session: AsyncSession) -> AdminGroupService:
    return AdminGroupService(PostgresAdminGroupRepository(session))


def get_broadcast_service(session: AsyncSession) -> BroadcastService:
    return BroadcastService(PostgresBroadcastRepository(session))


def get_lead_action_repo(session: AsyncSession) -> PostgresLeadActionRepository:
    return PostgresLeadActionRepository(session)


def get_lead_analytics_service(session: AsyncSession) -> "LeadAnalyticsService":
    from core.services.lead_analytics_service import LeadAnalyticsService
    return LeadAnalyticsService(
        action_repo=PostgresLeadActionRepository(session),
        lead_repo=PostgresLeadRepository(session),
    )


def get_audit_log_repo(session: AsyncSession) -> PostgresAuditLogRepository:
    return PostgresAuditLogRepository(session)


def get_pipeline_service(session: AsyncSession) -> PipelineService:
    return PipelineService(
        lead_repo=get_lead_repo(session),
        pipeline_repo=get_pipeline_repo(session),
        action_repo=PostgresLeadActionRepository(session),
        audit_repo=PostgresAuditLogRepository(session),
    )


def get_group_join_repo(session: AsyncSession) -> "PostgresGroupJoinRepository":
    from infrastructure.database.repositories.group_join_repo import PostgresGroupJoinRepository
    return PostgresGroupJoinRepository(session)


def get_stats_service(session: AsyncSession) -> "StatsService":
    from core.services.stats_service import StatsService
    from infrastructure.database.repositories.group_join_repo import PostgresGroupJoinRepository
    from shared.config import get_settings
    settings = get_settings()
    # Use the main customer group for join tracking; fall back to admin_group_id
    # if BOT_MAIN_GROUP_ID is not configured yet (backward-compat).
    tracked_group_id = settings.bot.main_group_id or settings.bot.admin_group_id
    return StatsService(
        session=session,
        join_repo=PostgresGroupJoinRepository(session),
        tracked_group_id=tracked_group_id,
    )


def get_lead_notification_service() -> "LeadNotificationService":
    """Return a LeadNotificationService wired with bot credentials from settings."""
    from core.services.lead_notification_service import LeadNotificationService
    from shared.config import get_settings
    settings = get_settings()
    return LeadNotificationService(
        admin_user_id=settings.bot.admin_user_id,
        bot_token=settings.bot.token.get_secret_value(),
    )


def get_blocked_chat_repo(session: AsyncSession) -> PostgresBlockedChatRepository:
    """Return a BlockedChatRepository for the given session."""
    return PostgresBlockedChatRepository(session)


def get_tactic_outcome_repo(session: AsyncSession) -> "PostgresTacticOutcomeRepository":
    from infrastructure.database.repositories.tactic_outcome_repo import PostgresTacticOutcomeRepository
    return PostgresTacticOutcomeRepository(session)


def get_journey_event_service(session: AsyncSession) -> "JourneyEventService":
    from core.services.journey_event_service import JourneyEventService
    return JourneyEventService(session)


def get_agent_memory_service(session: AsyncSession) -> "AgentMemoryService":
    from core.services.agent_memory_service import AgentMemoryService
    return AgentMemoryService(session)


def get_followup_scheduler_service(session: AsyncSession) -> "FollowupSchedulerService":
    from core.services.followup_scheduler_service import FollowupSchedulerService
    return FollowupSchedulerService(session)


def get_admin_escalation_service(session: AsyncSession) -> "AdminEscalationService":
    from core.services.admin_escalation_service import AdminEscalationService
    return AdminEscalationService(session)


def get_agent_decision_engine() -> "AgentDecisionEngine":
    from core.services import agent_decision_engine
    return agent_decision_engine


def get_lead_signal_service() -> "LeadSignalService":
    from core.services.lead_signal_service import LeadSignalService
    return LeadSignalService()


def get_dynamic_offer_service() -> "DynamicOfferService":
    from core.services.dynamic_offer_service import DynamicOfferService
    return DynamicOfferService()


def get_conversation_policy_service() -> "ConversationPolicyService":
    from core.services.conversation_policy_service import ConversationPolicyService
    return ConversationPolicyService()


def get_text_normalization_service() -> "TextNormalizationService":
    from core.services.text_normalization_service import TextNormalizationService
    return TextNormalizationService()


def get_agent_execution_sandbox_service() -> "AgentExecutionSandboxService":
    from core.services.agent_execution_sandbox_service import AgentExecutionSandboxService
    return AgentExecutionSandboxService()


def get_agent_execution_queue_service(session: AsyncSession) -> "AgentExecutionQueueService":
    from core.services.agent_execution_queue_service import AgentExecutionQueueService
    return AgentExecutionQueueService(session)


def get_agent_effective_settings_service(
    runtime_overrides: dict | None = None,
) -> "AgentEffectiveSettingsService":
    from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
    return AgentEffectiveSettingsService(runtime_overrides)


def get_agent_metrics_service(session: AsyncSession) -> "AgentMetricsService":
    from core.services.agent_metrics_service import AgentMetricsService
    return AgentMetricsService(session)


def get_agent_response_orchestrator() -> "AgentResponseOrchestrator":
    from core.services.agent_response_orchestrator import AgentResponseOrchestrator
    return AgentResponseOrchestrator()


def get_crm_contact_service(session: AsyncSession) -> "CRMContactService":
    from core.services.crm_contact_service import CRMContactService
    return CRMContactService(session)


def get_crm_message_service(session: AsyncSession) -> "CRMMessageService":
    from core.services.crm_message_service import CRMMessageService
    return CRMMessageService(session)


def get_admin_user_service(session: AsyncSession) -> "AdminUserService":
    from core.services.admin_user_service import AdminUserService
    return AdminUserService(session)


def get_admin_audit_log_service(session: AsyncSession) -> "AdminAuditLogService":
    from core.services.admin_audit_log_service import AdminAuditLogService
    return AdminAuditLogService(session)
