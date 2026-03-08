"""
core.services.user_followup_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Persistent, multi-stage follow-up messages sent directly to users.

Called by the scheduler every 3 minutes.  For each lead with an overdue
``user_followup_at``, sends the next stage message via the tenant's Bot
and advances the stage counter.

Stage progression:
  Stage 1 → 4h after last interaction (gentle reminder)
  Stage 2 → 24h after stage 1 (stronger value proposition)
  Stage 3 → 48h after stage 2 (final soft re-engagement, then close)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.logging import get_logger
from shared.templates.followup_templates import get_followup_message

log = get_logger(__name__)

# ── Timing constants (minutes) ──────────────────────────────────────────────

INITIAL_DELAY_MINUTES = 4 * 60       # 4 hours — first follow-up after silence
STAGE_DELAYS: dict[int, int] = {
    1: 24 * 60,   # 24 hours after stage 1 → stage 2
    2: 48 * 60,   # 48 hours after stage 2 → stage 3
}

# Safety cap: maximum leads to process per scheduler run
_BATCH_LIMIT = 50


class UserFollowupService:
    """Send staged re-engagement messages to idle leads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def process_due_user_followups(self) -> dict[str, int]:
        """Scan all due user follow-ups and send messages.

        Returns ``{sent: N, skipped: N, errors: N, closed: N}``.
        """
        from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

        now = datetime.now(timezone.utc)
        repo = PostgresLeadRepository(self._session)
        leads = await repo.get_due_user_followups(now, limit=_BATCH_LIMIT)

        if not leads:
            return {"sent": 0, "skipped": 0, "errors": 0, "closed": 0}

        counts = {"sent": 0, "skipped": 0, "errors": 0, "closed": 0}
        for lead in leads:
            try:
                await self._process_single(lead, repo, now)
                counts["sent"] += 1
            except Exception:
                log.warning("user_followup_failed", lead_id=lead.id)
                counts["errors"] += 1

        return counts

    async def _process_single(
        self, lead: object, repo: object, now: datetime,
    ) -> None:
        """Process a single lead: send message, advance stage."""
        next_stage = (lead.user_followup_stage or 0) + 1  # type: ignore[union-attr]

        # Determine business type for template
        business_type = await self._resolve_business_type(lead.tenant_id)  # type: ignore[union-attr]

        # Get message
        message_text = get_followup_message(
            stage=next_stage,
            business_type=business_type,
            name=lead.name,  # type: ignore[union-attr]
        )

        # Resolve Bot and send
        bot_token = await self._resolve_bot_token(lead.tenant_id)  # type: ignore[union-attr]
        await self._send_message(bot_token, lead.user_id, message_text)  # type: ignore[union-attr]

        # Advance stage
        if next_stage >= 3:
            # Final stage — close the follow-up flow
            await repo.update_user_followup(  # type: ignore[union-attr]
                lead.id,  # type: ignore[union-attr]
                user_followup_stage=next_stage,
                user_followup_at=None,
                user_followup_closed=True,
            )
            counts_key = "closed"
            log.info(
                "user_followup_closed",
                lead_id=lead.id,  # type: ignore[union-attr]
                stage=next_stage,
            )
        else:
            # Schedule next stage
            next_at = now + timedelta(minutes=STAGE_DELAYS[next_stage])
            await repo.update_user_followup(  # type: ignore[union-attr]
                lead.id,  # type: ignore[union-attr]
                user_followup_stage=next_stage,
                user_followup_at=next_at,
            )

        log.info(
            "user_followup_sent",
            lead_id=lead.id,  # type: ignore[union-attr]
            user_id=lead.user_id,  # type: ignore[union-attr]
            stage=next_stage,
            business_type=business_type,
            tenant_id=lead.tenant_id,  # type: ignore[union-attr]
        )

    async def _resolve_bot_token(self, tenant_id: int | None) -> str:
        """Get the Bot token for the tenant, or fall back to platform bot."""
        settings = get_settings()
        if tenant_id:
            from infrastructure.database.models.tenant import TenantModel
            tenant = await self._session.get(TenantModel, tenant_id)
            if tenant and getattr(tenant, "bot_token", None):
                return tenant.bot_token
        return settings.bot.token.get_secret_value()

    async def _resolve_business_type(self, tenant_id: int | None) -> str:
        """Get the business type for the tenant, or fall back to 'ceiling'."""
        if tenant_id:
            from infrastructure.database.models.tenant import TenantModel
            tenant = await self._session.get(TenantModel, tenant_id)
            if tenant:
                return getattr(tenant, "business_type", "ceiling") or "ceiling"
        return "ceiling"

    @staticmethod
    async def _send_message(bot_token: str, chat_id: int, text: str) -> None:
        """Send a message via a temporary Bot instance. Never raises."""
        from aiogram import Bot

        bot = Bot(token=bot_token)
        try:
            await bot.send_message(chat_id, text)
        finally:
            await bot.session.close()
