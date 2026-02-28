"""
core.services.lead_notification_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin-group notification service for new and HOT leads.

This service manages its own Bot lifecycle and DB sessions so it can be
called fire-and-forget after the main transaction has committed.

Public API
----------
  is_hot_lead(lead) -> bool               — pure predicate
  LeadNotificationService.notify_new_lead(lead)   — "🆕 Yangi lid" card
  LeadNotificationService.notify_hot_lead(lead_id) — "🔥 HOT LEAD" alert (deduped)
"""
from __future__ import annotations

from core.domain.lead import Lead
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.audit_log_repo import PostgresAuditLogRepository
from infrastructure.database.repositories.lead_action_repo import PostgresLeadActionRepository
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

HOT_SCORE_THRESHOLD = 7


def is_hot_lead(lead: Lead) -> bool:
    """Return True if the lead should trigger a HOT admin alert."""
    return lead.lead_status == "hot" or (lead.score or 0) >= HOT_SCORE_THRESHOLD


class LeadNotificationService:
    """
    Sends admin-group notifications for new and HOT leads.

    Each public method creates its own Bot instance + DB session so the
    caller never needs to worry about session state or Bot lifecycle.
    Methods never raise — all exceptions are caught and logged.
    """

    def __init__(self, admin_user_id: int, bot_token: str) -> None:
        self._admin_user_id = admin_user_id
        self._bot_token = bot_token

    # ── Public API ─────────────────────────────────────────────────────────────

    async def notify_new_lead(self, lead: Lead) -> None:
        """Send a NEW lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        text = self._new_lead_text(lead)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📌 Kanban'da ochish",
                callback_data=f"kanban:lead:{lead.id}:new",
            ),
        ]])

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, keyboard)
            await self._log_new_lead_action(lead.id)
        except Exception:
            log.exception("notify_new_lead_error", lead_id=lead.id)
        finally:
            await bot.session.close()

    async def notify_hot_lead(self, lead_id: int) -> None:
        """Send a HOT lead alert once, deduped by last_action. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        factory = get_session_factory()
        async with factory() as session:
            try:
                lead_repo = PostgresLeadRepository(session)
                lead = await lead_repo.get_by_id(lead_id)
                if lead is None:
                    log.warning("notify_hot_lead_not_found", lead_id=lead_id)
                    return
                if lead.last_action == "hot_alert_sent":
                    log.debug("notify_hot_lead_skipped_dedupe", lead_id=lead_id)
                    return

                text = self._hot_lead_text(lead)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📌 Kanban'da ochish",
                            callback_data=f"kanban:lead:{lead_id}:hot",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="✅ WON",
                            callback_data=f"kanban:move:{lead_id}:won",
                        ),
                        InlineKeyboardButton(
                            text="❌ LOST",
                            callback_data=f"kanban:move:{lead_id}:lost",
                        ),
                    ],
                ])

                bot = Bot(
                    token=self._bot_token,
                    default=DefaultBotProperties(parse_mode="HTML"),
                )
                try:
                    await self._send_to_groups_and_dm(bot, text, keyboard)

                    # Dedupe marker + audit trail (same session — atomic)
                    await lead_repo.update_last_action(lead_id, "hot_alert_sent")
                    await PostgresLeadActionRepository(session).insert(
                        lead_id, self._admin_user_id, "admin_notify_hot"
                    )
                    await PostgresAuditLogRepository(session).insert(
                        actor_id=self._admin_user_id,
                        action="lead.hot_alert_sent",
                        entity_type="lead",
                        entity_id=lead_id,
                        new_value={"last_action": "hot_alert_sent"},
                    )
                    await session.commit()
                except Exception:
                    log.exception("notify_hot_lead_error", lead_id=lead_id)
                    await session.rollback()
                finally:
                    await bot.session.close()

            except Exception:
                log.exception("notify_hot_lead_outer_error", lead_id=lead_id)

    # ── Internals ──────────────────────────────────────────────────────────────

    @staticmethod
    def _new_lead_text(lead: Lead) -> str:
        return (
            f"🆕 <b>Yangi lid keldi!</b>\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 {lead.name}\n"
            f"📱 {lead.phone}\n"
            f"📍 {lead.district}\n"
            f"🏷 {lead.category.value}\n\n"
            f"/lead_{lead.id}"
        )

    @staticmethod
    def _hot_lead_text(lead: Lead) -> str:
        score_tag = f" ⭐{lead.score}" if lead.score else ""
        pkg_tag = f"\n📦 Paket: {lead.package_type}" if lead.package_type else ""
        return (
            f"🔥 <b>HOT LEAD!</b>{score_tag}\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 {lead.name}\n"
            f"📱 {lead.phone}\n"
            f"📍 {lead.district}{pkg_tag}\n\n"
            f"/lead_{lead.id}"
        )

    async def _send_to_groups_and_dm(self, bot: object, text: str, keyboard: object) -> None:
        """Deliver *text*+*keyboard* to admin DM and all tracked admin groups."""
        # Admin DM
        try:
            await bot.send_message(self._admin_user_id, text, reply_markup=keyboard)  # type: ignore[union-attr]
        except Exception as exc:
            log.warning("notify_admin_dm_failed", error=str(exc))

        # Admin groups
        try:
            factory = get_session_factory()
            async with factory() as session:
                group_ids = await PostgresAdminGroupRepository(session).list_all_chat_ids()
        except Exception:
            log.exception("notify_get_groups_error")
            return

        admin_group_id = get_settings().bot.admin_group_id
        for gid in group_ids:
            # Hard whitelist: only send to the designated admin group.
            # Prevents the main customer group (BOT_MAIN_GROUP_ID) from
            # receiving lead cards even if it was previously recorded.
            if gid != admin_group_id:
                log.warning("notify_skip_non_admin_group", chat_id=gid)
                continue
            try:
                await bot.send_message(gid, text, reply_markup=keyboard)  # type: ignore[union-attr]
            except Exception as exc:
                log.warning("notify_group_failed", chat_id=gid, error=str(exc))

    async def _log_new_lead_action(self, lead_id: int) -> None:
        """Insert lead_action + audit_log for a new-lead notification."""
        factory = get_session_factory()
        async with factory() as session:
            try:
                await PostgresLeadActionRepository(session).insert(
                    lead_id, self._admin_user_id, "admin_notify_new"
                )
                await PostgresAuditLogRepository(session).insert(
                    actor_id=self._admin_user_id,
                    action="lead.admin_notify_new",
                    entity_type="lead",
                    entity_id=lead_id,
                )
                await session.commit()
            except Exception:
                log.exception("notify_log_new_lead_error", lead_id=lead_id)
