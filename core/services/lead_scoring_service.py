"""
core.services.lead_scoring_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unified async lead scoring service.

Single entry point for (re-)scoring a lead:
1. Loads lead + Redis memory + Redis session score
2. Runs the deterministic scoring engine
3. Persists all scoring columns atomically
4. Schedules follow-ups
5. Emits structured logs

Usage::

    from core.services.lead_scoring_service import LeadScoringService

    svc = LeadScoringService()
    result = await svc.rescore_lead(
        user_id=123,
        lead_temperature="warm",
        closing_confidence=0.6,
    )
"""
from __future__ import annotations

from typing import Any

from core.services.lead_scoring_engine import ScoringResult, score_lead
from shared.logging import get_logger

log = get_logger(__name__)


class LeadScoringService:
    """Async service wrapping the pure scoring engine with I/O operations.

    Stateless — instantiate per-call or cache at DI level.
    All methods fail silently (never raises to caller).
    """

    # ── Public API ────────────────────────────────────────────────────────

    async def rescore_lead(
        self,
        *,
        user_id: int,
        lead_temperature: str | None = None,
        closing_confidence: float | None = None,
        trigger: str = "ai_message",
    ) -> ScoringResult | None:
        """(Re-)score the latest lead for *user_id*.

        Args:
            user_id: Telegram user ID.
            lead_temperature: AI-provided temperature from latest response.
            closing_confidence: AI-provided confidence from latest response.
            trigger: What caused the re-score (for logging).

        Returns:
            ScoringResult on success, None on failure or no lead found.
        """
        try:
            return await self._do_rescore(
                user_id=user_id,
                lead_temperature=lead_temperature,
                closing_confidence=closing_confidence,
                trigger=trigger,
            )
        except Exception:
            log.warning("lead_scoring_failed", user_id=user_id, trigger=trigger)
            return None

    async def rescore_lead_by_id(
        self,
        *,
        lead_id: int,
        user_id: int,
        trigger: str = "manual",
    ) -> ScoringResult | None:
        """Re-score a specific lead by its DB id.

        Loads the lead directly, reads Redis memory for the user,
        runs the engine, and persists.
        """
        try:
            return await self._do_rescore_by_lead_id(
                lead_id=lead_id,
                user_id=user_id,
                trigger=trigger,
            )
        except Exception:
            log.warning("lead_scoring_by_id_failed", lead_id=lead_id, trigger=trigger)
            return None

    # ── Internal ──────────────────────────────────────────────────────────

    async def _do_rescore(
        self,
        *,
        user_id: int,
        lead_temperature: str | None,
        closing_confidence: float | None,
        trigger: str,
    ) -> ScoringResult | None:
        from infrastructure.database.session import get_session_factory
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            leads = await repo.list_by_user(user_id, limit=1)
            if not leads:
                return None
            lead = leads[0]

            # Cancel active user-followup on re-engagement
            if (lead.user_followup_stage or 0) > 0:
                log.info(
                    "user_followup_reengaged",
                    lead_id=lead.id,
                    stage=lead.user_followup_stage,
                )
                await repo.update_user_followup(
                    lead.id,
                    user_followup_stage=0,
                    user_followup_at=None,
                )

            # Gather all signals
            mem = await self._load_redis_memory(user_id)
            redis_score = await self._get_redis_score(user_id)
            raw_score = max(redis_score, lead.score or 0)

            scoring = score_lead(
                raw_score=raw_score,
                closing_confidence=closing_confidence,
                phone_captured=bool(lead.phone and lead.phone != "\u2014"),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district and lead.district != "Noma\u02bblum"),
                design_type=mem.get("design_type"),
                intent=mem.get("last_intent"),
                last_objection=mem.get("last_objection"),
                closing_attempted=bool(mem.get("last_closing_attempt")),
                follow_up_count=lead.follow_up_count or 0,
                package_type=lead.package_type,
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                assigned_manager_id=lead.assigned_manager_id,
            )

            # Follow-up scheduling
            next_fu = await self._compute_followup(
                lead=lead,
                mem=mem,
                scoring=scoring,
                closing_confidence=closing_confidence,
                lead_temperature=lead_temperature,
                user_id=user_id,
            )

            # Persist atomically
            await repo.update_scoring_engine(
                lead.id,
                score=scoring.score,
                lead_temperature=scoring.lead_temperature,
                closing_confidence=closing_confidence,
                urgency_signal=scoring.urgency_signal,
                budget_signal=scoring.budget_signal,
                engagement_signal=scoring.engagement_signal,
                objection_signal=scoring.objection_signal,
                scoring_reasons=scoring.scoring_reasons,
                operator_attention=scoring.operator_attention,
                next_follow_up_at=next_fu,
            )

            # Structured logging
            self._log_scoring(lead, scoring, trigger)

            # Schedule user followup if eligible
            await self._maybe_schedule_user_followup(
                repo, lead, scoring,
            )

            await session.commit()

        # Auto-assign if lead became HOT or needs attention and is unassigned
        self._maybe_auto_assign(lead, scoring)

        return scoring

    async def _do_rescore_by_lead_id(
        self,
        *,
        lead_id: int,
        user_id: int,
        trigger: str,
    ) -> ScoringResult | None:
        from infrastructure.database.session import get_session_factory
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            lead = await repo.get_by_id(lead_id)
            if not lead:
                return None

            mem = await self._load_redis_memory(user_id)
            redis_score = await self._get_redis_score(user_id)
            raw_score = max(redis_score, lead.score or 0)

            scoring = score_lead(
                raw_score=raw_score,
                phone_captured=bool(lead.phone and lead.phone != "\u2014"),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district and lead.district != "Noma\u02bblum"),
                design_type=mem.get("design_type"),
                intent=mem.get("last_intent"),
                last_objection=mem.get("last_objection"),
                closing_attempted=bool(mem.get("last_closing_attempt")),
                follow_up_count=lead.follow_up_count or 0,
                package_type=lead.package_type,
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                assigned_manager_id=lead.assigned_manager_id,
            )

            await repo.update_scoring_engine(
                lead.id,
                score=scoring.score,
                lead_temperature=scoring.lead_temperature,
                urgency_signal=scoring.urgency_signal,
                budget_signal=scoring.budget_signal,
                engagement_signal=scoring.engagement_signal,
                objection_signal=scoring.objection_signal,
                scoring_reasons=scoring.scoring_reasons,
                operator_attention=scoring.operator_attention,
            )

            self._log_scoring(lead, scoring, trigger)
            await session.commit()

        return scoring

    # ── Redis helpers ─────────────────────────────────────────────────────

    @staticmethod
    async def _load_redis_memory(user_id: int) -> dict[str, Any]:
        try:
            from apps.bot.handlers.private.ai_memory import _load_ai_memory
            return await _load_ai_memory(user_id)
        except Exception:
            return {}

    @staticmethod
    async def _get_redis_score(user_id: int) -> int:
        try:
            from apps.bot.handlers.private.ai_scoring import _get_lead_score
            return await _get_lead_score(user_id)
        except Exception:
            return 0

    # ── Follow-up scheduling ──────────────────────────────────────────────

    @staticmethod
    async def _compute_followup(
        *,
        lead: Any,
        mem: dict[str, Any],
        scoring: ScoringResult,
        closing_confidence: float | None,
        lead_temperature: str | None,
        user_id: int,
    ) -> Any:
        """Try brain-driven scheduling, fall back to simple delay."""
        import asyncio
        from shared.utils.lead_scoring import compute_next_followup

        next_fu = None
        try:
            from core.services.followup_brain_service import decide_follow_up
            from apps.bot.handlers.private.ai_memory import _save_ai_memory

            brain = decide_follow_up(
                score=scoring.score,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                has_district=bool(lead.district),
                follow_up_count=lead.follow_up_count or 0,
                closing_confidence=closing_confidence,
                lead_temperature=lead_temperature,
                last_objection=mem.get("last_objection"),
                buyer_type=mem.get("buyer_type"),
                last_activity_ts=mem.get("updated_at"),
            )
            if brain.should_follow_up and brain.follow_up_delay_minutes:
                from datetime import datetime, timedelta, timezone
                next_fu = datetime.now(timezone.utc) + timedelta(
                    minutes=brain.follow_up_delay_minutes,
                )
                mem["last_fu_type"] = brain.follow_up_type
                asyncio.create_task(_save_ai_memory(user_id, mem))
        except Exception:
            pass

        if next_fu is None:
            next_fu = compute_next_followup(
                scoring.lead_temperature, closing_confidence,
            )

        return next_fu

    @staticmethod
    async def _maybe_schedule_user_followup(
        repo: Any,
        lead: Any,
        scoring: ScoringResult,
    ) -> None:
        """Schedule initial user follow-up if eligible."""
        if (
            (scoring.lead_temperature in ("hot", "warm") or scoring.score >= 10)
            and not lead.user_followup_closed
            and (lead.user_followup_stage or 0) == 0
        ):
            from datetime import datetime, timedelta, timezone
            await repo.update_user_followup(
                lead.id,
                user_followup_at=datetime.now(timezone.utc) + timedelta(hours=4),
            )

    # ── Logging ───────────────────────────────────────────────────────────

    @staticmethod
    def _log_scoring(lead: Any, scoring: ScoringResult, trigger: str) -> None:
        log.info(
            "lead_scored",
            lead_id=lead.id,
            score=scoring.score,
            temperature=scoring.lead_temperature,
            urgency=scoring.urgency_signal,
            trigger=trigger,
        )

        old_temp = getattr(lead, "lead_temperature", None) or ""
        if scoring.lead_temperature != old_temp:
            log.info(
                "lead_temperature_changed",
                lead_id=lead.id,
                old=old_temp,
                new=scoring.lead_temperature,
            )

        if scoring.lead_temperature == "hot" and old_temp != "hot":
            log.info(
                "lead_promoted_to_hot",
                lead_id=lead.id,
                score=scoring.score,
                reasons=scoring.scoring_reasons,
                trigger=trigger,
            )

        if scoring.operator_attention and not getattr(lead, "operator_attention", False):
            log.info(
                "lead_needs_operator",
                lead_id=lead.id,
                score=scoring.score,
                reasons=scoring.scoring_reasons,
            )

    # ── Auto-assignment trigger ──────────────────────────────────────────

    @staticmethod
    def _maybe_auto_assign(lead: Any, scoring: ScoringResult) -> None:
        """Fire-and-forget auto-assignment when lead becomes HOT or needs attention."""
        if lead.assigned_manager_id:
            return  # already assigned

        old_temp = getattr(lead, "lead_temperature", None) or ""
        promoted_to_hot = scoring.lead_temperature == "hot" and old_temp != "hot"
        new_attention = scoring.operator_attention and not getattr(
            lead, "operator_attention", False,
        )

        if not (promoted_to_hot or new_attention):
            return

        tenant_id = getattr(lead, "tenant_id", None)
        if not tenant_id:
            return

        reason = "auto_hot_promotion" if promoted_to_hot else "auto_attention_queue"

        import asyncio
        asyncio.create_task(_auto_assign_background(lead.id, tenant_id, reason))


# ── Module-level helper (outside the class) ──────────────────────────────────


async def _auto_assign_background(
    lead_id: int, tenant_id: int, reason: str,
) -> None:
    """Try round-robin auto-assignment. Falls back to attention queue silently."""
    try:
        from core.services.operator_assignment_service import OperatorAssignmentService
        svc = OperatorAssignmentService()
        result = await svc.auto_assign_round_robin(
            lead_id=lead_id,
            tenant_id=tenant_id,
            reason=reason,
        )
        if not result:
            log.info(
                "auto_assign_fallback_attention_queue",
                lead_id=lead_id,
                tenant_id=tenant_id,
                reason=reason,
            )
    except Exception:
        log.warning("auto_assign_background_failed", lead_id=lead_id)
