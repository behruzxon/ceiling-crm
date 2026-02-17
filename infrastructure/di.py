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
from core.services.broadcast_service import BroadcastService
from core.services.crm_service import CRMService
from core.services.lead_service import LeadService
from core.services.user_service import UserService
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.repositories.pipeline_repo import PostgresPipelineRepository
from infrastructure.database.repositories.user_repo import PostgresUserRepository


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


def get_crm_service(session: AsyncSession) -> CRMService:
    return CRMService(
        lead_repo=get_lead_repo(session),
        pipeline_repo=get_pipeline_repo(session),
        event_bus=event_bus,
    )
