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
from core.services.user_service import UserService
from core.services.warranty_service import WarrantyService
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.broadcast_repo import PostgresBroadcastRepository
from infrastructure.database.repositories.group_settings_repo import PostgresGroupSettingsRepository
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
