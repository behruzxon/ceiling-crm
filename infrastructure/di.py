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

from sqlalchemy import select
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


def get_user_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresUserRepository:
    return PostgresUserRepository(session, tenant_id)


def get_lead_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresLeadRepository:
    return PostgresLeadRepository(session, tenant_id)


def get_pipeline_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresPipelineRepository:
    return PostgresPipelineRepository(session, tenant_id)


def get_user_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> UserService:
    return UserService(get_user_repo(session, tenant_id))


def get_lead_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> LeadService:
    return LeadService(
        lead_repo=get_lead_repo(session, tenant_id),
        pipeline_repo=get_pipeline_repo(session, tenant_id),
        event_bus=event_bus,
        action_repo=PostgresLeadActionRepository(session, tenant_id),
    )


def get_group_settings_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> GroupSettingsService:
    return GroupSettingsService(PostgresGroupSettingsRepository(session, tenant_id))


def get_payment_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> PaymentService:
    return PaymentService(PostgresPaymentRepository(session, tenant_id))


def get_warranty_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> WarrantyService:
    return WarrantyService(PostgresWarrantyRepository(session, tenant_id))


def get_crm_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> CRMService:
    return CRMService(
        lead_repo=get_lead_repo(session, tenant_id),
        pipeline_repo=get_pipeline_repo(session, tenant_id),
        event_bus=event_bus,
    )


def get_admin_group_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> AdminGroupService:
    return AdminGroupService(PostgresAdminGroupRepository(session, tenant_id))


def get_broadcast_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> BroadcastService:
    return BroadcastService(PostgresBroadcastRepository(session, tenant_id))


def get_lead_action_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresLeadActionRepository:
    return PostgresLeadActionRepository(session, tenant_id)


def get_lead_analytics_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> "LeadAnalyticsService":
    from core.services.lead_analytics_service import LeadAnalyticsService
    return LeadAnalyticsService(
        action_repo=PostgresLeadActionRepository(session, tenant_id),
        lead_repo=PostgresLeadRepository(session, tenant_id),
    )


def get_audit_log_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresAuditLogRepository:
    return PostgresAuditLogRepository(session, tenant_id)


def get_pipeline_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> PipelineService:
    return PipelineService(
        lead_repo=get_lead_repo(session, tenant_id),
        pipeline_repo=get_pipeline_repo(session, tenant_id),
        action_repo=PostgresLeadActionRepository(session, tenant_id),
        audit_repo=PostgresAuditLogRepository(session, tenant_id),
    )


def get_group_join_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> "PostgresGroupJoinRepository":
    from infrastructure.database.repositories.group_join_repo import PostgresGroupJoinRepository
    return PostgresGroupJoinRepository(session, tenant_id)


def get_stats_service(
    session: AsyncSession, tenant_id: int | None = None,
) -> "StatsService":
    from core.services.stats_service import StatsService
    from infrastructure.database.repositories.group_join_repo import PostgresGroupJoinRepository
    from shared.config import get_settings
    settings = get_settings()
    # Use the main customer group for join tracking; fall back to admin_group_id
    # if BOT_MAIN_GROUP_ID is not configured yet (backward-compat).
    tracked_group_id = settings.bot.main_group_id or settings.bot.admin_group_id
    return StatsService(
        session=session,
        join_repo=PostgresGroupJoinRepository(session, tenant_id),
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


def get_blocked_chat_repo(
    session: AsyncSession, tenant_id: int | None = None,
) -> PostgresBlockedChatRepository:
    """Return a BlockedChatRepository for the given session."""
    return PostgresBlockedChatRepository(session, tenant_id)


async def get_tenant_menu_config(
    session: AsyncSession, tenant_id: int | None,
) -> dict | None:
    """Fetch menu_config JSONB from the tenant record.

    Returns None when *tenant_id* is falsy or the tenant row doesn't exist,
    which signals callers to fall back to the hardcoded default menu.
    """
    if not tenant_id:
        return None
    from infrastructure.database.models.tenant import TenantModel

    result = await session.execute(
        select(TenantModel.menu_config).where(TenantModel.id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_tenant_ai_config(
    session: AsyncSession, tenant_id: int | None,
) -> tuple[str | None, str | None]:
    """Fetch AI prompt fields from the tenant record.

    Returns ``(ai_system_prompt, knowledge_base)`` — both may be *None*,
    which signals callers to fall back to the hardcoded defaults.
    """
    if not tenant_id:
        return None, None
    from infrastructure.database.models.tenant import TenantModel

    result = await session.execute(
        select(
            TenantModel.ai_system_prompt,
            TenantModel.knowledge_base,
        ).where(TenantModel.id == tenant_id)
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    return row[0], row[1]


def get_ai_knowledge_repo(
    session: AsyncSession,
    tenant_id: int | None = None,
) -> "PostgresAiKnowledgeRepository":
    from infrastructure.database.repositories.ai_knowledge_repo import PostgresAiKnowledgeRepository
    return PostgresAiKnowledgeRepository(session, tenant_id)


def get_lead_scoring_service() -> "LeadScoringService":
    from core.services.lead_scoring_service import LeadScoringService
    return LeadScoringService()


def get_operator_assignment_service() -> "OperatorAssignmentService":
    from core.services.operator_assignment_service import OperatorAssignmentService
    return OperatorAssignmentService()


def get_tenant_repo(session: AsyncSession) -> "PostgresTenantRepository":
    from infrastructure.database.repositories.tenant_repo import PostgresTenantRepository
    return PostgresTenantRepository(session)


def get_tenant_service(session: AsyncSession) -> "TenantService":
    from core.services.tenant_service import TenantService
    return TenantService(get_tenant_repo(session))


def get_billing_service(session: AsyncSession) -> "BillingService":
    from core.services.billing_service import BillingService
    return BillingService(session)


def get_subscription_payment_repo(
    session: AsyncSession,
    tenant_id: int | None = None,
) -> "PostgresSubscriptionPaymentRepository":
    from infrastructure.database.repositories.subscription_payment_repo import (
        PostgresSubscriptionPaymentRepository,
    )
    return PostgresSubscriptionPaymentRepository(session, tenant_id)


def get_subscription_billing_service(
    session: AsyncSession,
    tenant_id: int | None = None,
) -> "SubscriptionBillingService":
    from core.services.subscription_billing_service import SubscriptionBillingService
    return SubscriptionBillingService(
        session=session,
        payment_repo=get_subscription_payment_repo(session, tenant_id),
    )


def get_tenant_bot_service(session: AsyncSession) -> "TenantBotService":
    from core.services.tenant_bot_service import TenantBotService
    return TenantBotService(session)
