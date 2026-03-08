"""TenantService -- tenant creation and lookup."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logging import get_logger

if TYPE_CHECKING:
    from core.repositories.tenant_repo import AbstractTenantRepository
    from infrastructure.database.models.tenant import TenantModel

log = get_logger(__name__)


class TenantService:
    def __init__(self, tenant_repo: AbstractTenantRepository) -> None:
        self._repo = tenant_repo

    async def get_by_admin_user(self, admin_user_id: int) -> TenantModel | None:
        return await self._repo.get_by_admin_user_id(admin_user_id)

    async def slug_exists(self, slug: str) -> bool:
        return await self._repo.slug_exists(slug)

    async def create_tenant(self, tenant: TenantModel) -> TenantModel:
        result = await self._repo.create(tenant)
        log.info("tenant_created", tenant_id=result.id, slug=result.slug)
        return result

    async def update_tenant_field(
        self, admin_user_id: int, **fields: Any,
    ) -> TenantModel | None:
        """Update one or more fields on the tenant owned by *admin_user_id*.

        Accepts arbitrary keyword arguments matching TenantModel column names.
        Returns the updated tenant, or None if the user has no tenant.
        """
        tenant = await self._repo.get_by_admin_user_id(admin_user_id)
        if not tenant:
            return None
        for key, value in fields.items():
            setattr(tenant, key, value)
        result = await self._repo.update(tenant)
        log.info("tenant_field_updated", tenant_id=result.id, fields=list(fields.keys()))
        return result
