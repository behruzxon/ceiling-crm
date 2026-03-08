"""Reusable tenant-scoping mixin for repositories.

Provides constructor-level ``tenant_id`` binding so that every query method
automatically filters by the active tenant when running in multi-tenant mode.

When ``tenant_id`` is ``None`` (single-tenant / backward-compat) no filter
is applied and the repo behaves exactly as before.
"""
from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

_T = TypeVar("_T")


class TenantScopedRepository:
    """Mixin that injects tenant isolation into concrete repositories.

    Usage::

        class PostgresLeadRepository(TenantScopedRepository, AbstractLeadRepository):
            def __init__(self, session, tenant_id=None):
                super().__init__(session, tenant_id)

    Helper methods
    ~~~~~~~~~~~~~~
    * ``_apply_tenant_filter(stmt, model_class)`` — append
      ``WHERE model.tenant_id = :tid`` when scoped.
    * ``_resolve_tenant_id(override)`` — use explicit override or fall back
      to the constructor value.
    * ``_stamp_tenant_id(model)`` — set ``model.tenant_id`` on INSERT when
      the model doesn't already carry one.
    """

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ── Query filter ──────────────────────────────────────────────────────

    def _apply_tenant_filter(self, stmt: Select, model_class: Any) -> Select:
        """Append ``WHERE model_class.tenant_id == self._tenant_id``.

        No-op when ``_tenant_id`` is ``None`` (single-tenant mode).
        """
        if self._tenant_id is not None:
            return stmt.where(model_class.tenant_id == self._tenant_id)
        return stmt

    # ── Resolve override vs. constructor ──────────────────────────────────

    def _resolve_tenant_id(self, override: int | None = None) -> int | None:
        """Return *override* if given, else the constructor-level tenant_id."""
        return override if override is not None else self._tenant_id

    # ── Stamp on INSERT ───────────────────────────────────────────────────

    def _stamp_tenant_id(self, model: Any) -> None:
        """Set ``model.tenant_id`` from the constructor value.

        Only acts when the model attribute exists, is currently ``None``,
        and the repository was constructed with a non-None tenant_id.
        """
        if self._tenant_id is not None and hasattr(model, "tenant_id"):
            if model.tenant_id is None:
                model.tenant_id = self._tenant_id
