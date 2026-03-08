"""
core.services.operator_assignment_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator assignment for leads — manual, round-robin auto-assignment,
and attention queue management.

Operators are users with MANAGER (or higher) role within the same tenant.
"""
from __future__ import annotations

from typing import Any

from core.domain.lead import Lead
from core.domain.user import User
from shared.logging import get_logger

log = get_logger(__name__)


class OperatorAssignmentService:
    """Stateless service for lead-to-operator assignment.

    Instantiate per-call or cache at DI level.
    All public methods are async and open their own DB sessions
    so callers can fire-and-forget.
    """

    # ── Public API ────────────────────────────────────────────────────────

    async def assign_lead(
        self,
        *,
        lead_id: int,
        operator_id: int,
        reason: str = "manual",
        actor_id: int,
        tenant_id: int | None = None,
        notify: bool = True,
    ) -> Lead | None:
        """Assign *lead_id* to *operator_id*. Returns updated Lead or None on failure."""
        try:
            return await self._do_assign(
                lead_id=lead_id,
                operator_id=operator_id,
                reason=reason,
                actor_id=actor_id,
                tenant_id=tenant_id,
                notify=notify,
            )
        except Exception:
            log.warning("assign_lead_failed", lead_id=lead_id, operator_id=operator_id)
            return None

    async def reassign_lead(
        self,
        *,
        lead_id: int,
        new_operator_id: int,
        reason: str = "reassigned",
        actor_id: int,
        tenant_id: int | None = None,
        notify: bool = True,
    ) -> Lead | None:
        """Reassign *lead_id* to a different operator."""
        try:
            return await self._do_assign(
                lead_id=lead_id,
                operator_id=new_operator_id,
                reason=reason,
                actor_id=actor_id,
                tenant_id=tenant_id,
                notify=notify,
                is_reassign=True,
            )
        except Exception:
            log.warning("reassign_lead_failed", lead_id=lead_id, new_operator_id=new_operator_id)
            return None

    async def unassign_lead(
        self,
        *,
        lead_id: int,
        actor_id: int,
        tenant_id: int | None = None,
    ) -> Lead | None:
        """Remove operator assignment from *lead_id*."""
        try:
            return await self._do_unassign(
                lead_id=lead_id,
                actor_id=actor_id,
                tenant_id=tenant_id,
            )
        except Exception:
            log.warning("unassign_lead_failed", lead_id=lead_id)
            return None

    async def auto_assign_round_robin(
        self,
        *,
        lead_id: int,
        tenant_id: int,
        reason: str = "auto_round_robin",
    ) -> Lead | None:
        """Try to auto-assign *lead_id* to the next available operator via round-robin.

        Returns the updated Lead if assignment succeeded, None if no operators available.
        """
        try:
            return await self._do_auto_assign(
                lead_id=lead_id,
                tenant_id=tenant_id,
                reason=reason,
            )
        except Exception:
            log.warning("auto_assign_failed", lead_id=lead_id, tenant_id=tenant_id)
            return None

    async def get_attention_queue(
        self,
        tenant_id: int,
        limit: int = 20,
    ) -> list[Lead]:
        """Return leads that need operator attention for a tenant."""
        try:
            from infrastructure.database.session import get_session_factory
            from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

            factory = get_session_factory()
            async with factory() as session:
                repo = PostgresLeadRepository(session, tenant_id)
                return await repo.get_attention_leads(
                    tenant_id=tenant_id, limit=limit,
                )
        except Exception:
            log.warning("get_attention_queue_failed", tenant_id=tenant_id)
            return []

    async def get_assigned_leads(
        self,
        operator_id: int,
        tenant_id: int | None = None,
        limit: int = 20,
    ) -> list[Lead]:
        """Return leads assigned to a specific operator."""
        try:
            from infrastructure.database.session import get_session_factory
            from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

            factory = get_session_factory()
            async with factory() as session:
                repo = PostgresLeadRepository(session, tenant_id)
                return await repo.get_assigned_leads(
                    operator_id, tenant_id=tenant_id, limit=limit,
                )
        except Exception:
            log.warning("get_assigned_leads_failed", operator_id=operator_id)
            return []

    async def get_available_operators(
        self,
        tenant_id: int,
    ) -> list[User]:
        """Return MANAGER-role users for the tenant (available for assignment)."""
        try:
            from infrastructure.database.session import get_session_factory
            from infrastructure.di import get_user_service

            factory = get_session_factory()
            async with factory() as session:
                svc = get_user_service(session, tenant_id)
                return await svc.get_managers()
        except Exception:
            log.warning("get_available_operators_failed", tenant_id=tenant_id)
            return []

    # ── Internal ──────────────────────────────────────────────────────────

    async def _do_assign(
        self,
        *,
        lead_id: int,
        operator_id: int,
        reason: str,
        actor_id: int,
        tenant_id: int | None,
        notify: bool = True,
        is_reassign: bool = False,
    ) -> Lead:
        from infrastructure.database.session import get_session_factory
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session, tenant_id)
            lead = await repo.get_by_id(lead_id)
            if not lead:
                raise ValueError(f"Lead {lead_id} not found")

            old_operator = lead.assigned_manager_id
            updated = await repo.assign_manager(
                lead_id, operator_id, reason=reason,
            )
            await session.commit()

        action = "lead_reassigned" if is_reassign else "lead_assigned"
        log.info(
            action,
            lead_id=lead_id,
            operator_id=operator_id,
            old_operator=old_operator,
            reason=reason,
            actor_id=actor_id,
        )

        if notify:
            import asyncio
            asyncio.create_task(
                self._notify_operator(
                    operator_id=operator_id,
                    lead=updated,
                    is_reassign=is_reassign,
                )
            )

        return updated

    async def _do_unassign(
        self,
        *,
        lead_id: int,
        actor_id: int,
        tenant_id: int | None,
    ) -> Lead:
        from infrastructure.database.session import get_session_factory
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session, tenant_id)
            lead = await repo.get_by_id(lead_id)
            if not lead:
                raise ValueError(f"Lead {lead_id} not found")

            old_operator = lead.assigned_manager_id
            updated = await repo.unassign_manager(lead_id)
            await session.commit()

        log.info(
            "lead_unassigned",
            lead_id=lead_id,
            old_operator=old_operator,
            actor_id=actor_id,
        )
        return updated

    async def _do_auto_assign(
        self,
        *,
        lead_id: int,
        tenant_id: int,
        reason: str,
    ) -> Lead | None:
        """Round-robin: pick the operator with fewest active assigned leads."""
        from infrastructure.database.session import get_session_factory
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
        from infrastructure.di import get_user_service
        from sqlalchemy import select, func
        from infrastructure.database.models.lead import LeadModel

        factory = get_session_factory()
        async with factory() as session:
            # Get available operators for this tenant
            svc = get_user_service(session, tenant_id)
            operators = await svc.get_managers()
            if not operators:
                log.info(
                    "auto_assign_no_operators",
                    lead_id=lead_id,
                    tenant_id=tenant_id,
                )
                return None

            # Count active leads per operator (round-robin by least-loaded)
            operator_ids = [op.id for op in operators]
            count_stmt = (
                select(
                    LeadModel.assigned_manager_id,
                    func.count().label("cnt"),
                )
                .where(
                    LeadModel.assigned_manager_id.in_(operator_ids),
                    LeadModel.tenant_id == tenant_id,
                )
                .group_by(LeadModel.assigned_manager_id)
            )
            result = await session.execute(count_stmt)
            load_map: dict[int, int] = {
                row[0]: row[1] for row in result.all()
            }

            # Pick operator with fewest leads
            best_op = min(operators, key=lambda op: load_map.get(op.id, 0))

            repo = PostgresLeadRepository(session, tenant_id)
            updated = await repo.assign_manager(
                lead_id, best_op.id, reason=reason,
            )
            await session.commit()

        log.info(
            "lead_auto_assigned",
            lead_id=lead_id,
            operator_id=best_op.id,
            operator_name=best_op.first_name,
            reason=reason,
            tenant_id=tenant_id,
            operator_load=load_map.get(best_op.id, 0),
        )

        import asyncio
        asyncio.create_task(
            self._notify_operator(
                operator_id=best_op.id,
                lead=updated,
                is_reassign=False,
            )
        )

        return updated

    # ── Notification ──────────────────────────────────────────────────────

    @staticmethod
    async def _notify_operator(
        *,
        operator_id: int,
        lead: Lead,
        is_reassign: bool = False,
    ) -> None:
        """Send Telegram notification to the assigned operator. Never raises."""
        try:
            from shared.config import get_settings
            from aiogram import Bot

            settings = get_settings()
            bot = Bot(token=settings.bot.token.get_secret_value())

            action = "qayta tayinlandi" if is_reassign else "tayinlandi"
            temp_icon = {"hot": "🔥", "warm": "🌡", "cold": "❄️"}.get(
                lead.lead_temperature or "", "",
            )
            score_str = f"{lead.score}pt" if lead.score else ""
            attn = " ⚠️" if lead.operator_attention else ""

            text = (
                f"📋 Lid #{lead.id} sizga {action}\n"
                f"👤 {lead.name}\n"
                f"📱 {lead.phone}\n"
                f"📍 {lead.district}\n"
                f"{temp_icon} {score_str}{attn}\n"
            )
            if lead.assignment_reason:
                text += f"📝 Sabab: {lead.assignment_reason}\n"

            async with bot.session:
                await bot.send_message(operator_id, text)

            log.debug(
                "operator_notified",
                operator_id=operator_id,
                lead_id=lead.id,
            )
        except Exception:
            log.warning(
                "operator_notification_failed",
                operator_id=operator_id,
                lead_id=lead.id,
            )
