"""
Agent pipeline helpers extracted from ai_support.py.
Fire-and-forget lead signal extraction and orchestrator calls.
"""
from __future__ import annotations

from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)


async def _run_orchestrator(user_id: int, text: str) -> None:
    """Run agent orchestrator pipeline and persist trace (fire-and-forget)."""
    try:
        settings = get_settings()
        biz = settings.business
        if not biz.agent_response_orchestrator_enabled:
            return

        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem: dict = {"followup_enabled": True, "memory_data": {}}
        try:
            factory = get_session_factory()
            async with factory() as session:
                from core.services.agent_memory_service import AgentMemoryService
                svc = AgentMemoryService(session)
                db_mem = await svc.get_or_create(user_id)
                mem = {
                    "followup_enabled": db_mem.followup_enabled,
                    "followup_count": db_mem.followup_count,
                    "lead_temperature": db_mem.lead_temperature,
                    "phone_masked": db_mem.phone_masked,
                    "area_m2": db_mem.area_m2,
                    "memory_data": dict(db_mem.memory_data or {}),
                    "telegram_user_id": user_id,
                }
        except Exception:
            pass

        payload = AgentResponseOrchestrator.run_pipeline(
            memory=mem, text=text,
        )

        if biz.agent_response_orchestrator_trace_enabled:
            try:
                factory = get_session_factory()
                async with factory() as session:
                    from core.services.agent_memory_service import AgentMemoryService
                    svc = AgentMemoryService(session)
                    db_mem = await svc.get_or_create(user_id)
                    md = dict(db_mem.memory_data or {})
                    md = AgentResponseOrchestrator.persist_trace(md, payload)
                    db_mem.memory_data = md
                    await session.commit()
            except Exception:
                pass
    except Exception:
        log.debug("orchestrator_run_failed", user_id=user_id)


async def _process_lead_signal(user_id: int, text: str) -> None:
    """Extract intent/objection/urgency signals and persist to agent memory."""
    try:
        settings = get_settings()
        if not settings.business.agent_lead_signal_enabled:
            return

        from core.services.lead_signal_service import LeadSignalService

        signal = LeadSignalService.extract_signals(text)

        if signal.confidence_score < settings.business.agent_lead_signal_min_confidence:
            return

        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_memory_service import AgentMemoryService

            mem_svc = AgentMemoryService(session)
            mem = await mem_svc.get_or_create(user_id)

            md = dict(mem.memory_data or {})
            md = LeadSignalService.update_memory_from_signal(md, signal)
            mem.memory_data = md

            if signal.area_m2 is not None:
                mem.area_m2 = signal.area_m2

            if signal.should_disable_followup:
                mem.followup_enabled = False
                mem.stop_reason = "user_stop_signal"
                from core.services.followup_scheduler_service import FollowupSchedulerService
                fu_svc = FollowupSchedulerService(session)
                await fu_svc.cancel_all_pending(user_id, "user_stop_signal")

            await session.commit()
    except Exception:
        log.debug("lead_signal_processing_failed", user_id=user_id)
