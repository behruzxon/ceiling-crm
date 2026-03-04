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

    @staticmethod
    def _lead_status_keyboard(lead_id: int) -> "InlineKeyboardMarkup":
        """Build the quick-action inline keyboard appended to every lead card."""
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📌 Kanban'da ochish",
                    callback_data=f"kanban:lead:{lead_id}:new",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Bog'landim",
                    callback_data=f"lead:{lead_id}:status:contacted",
                ),
                InlineKeyboardButton(
                    text="📅 O'lchov",
                    callback_data=f"lead:{lead_id}:status:measurement",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Narx yuborildi",
                    callback_data=f"lead:{lead_id}:status:quoted",
                ),
                InlineKeyboardButton(
                    text="🧾 Zakaz",
                    callback_data=f"lead:{lead_id}:status:deal",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Yo'qotildi",
                    callback_data=f"lead:{lead_id}:status:lost",
                ),
            ],
        ])

    async def notify_new_lead(self, lead: Lead) -> None:
        """Send a NEW lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        text = self._new_lead_text(lead)
        keyboard = self._lead_status_keyboard(lead.id)

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
                keyboard = self._lead_status_keyboard(lead_id)

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
        dims = ""
        if lead.room_length and lead.room_width:
            dims = f"\n📐 O'lcham: {lead.room_length} × {lead.room_width} m"
        temp_tag = f"\n🌡 Holat: {lead.lead_temperature}" if lead.lead_temperature else ""
        conf_tag = (
            f"\n💡 Ishonch: {lead.closing_confidence:.0%}"
            if lead.closing_confidence is not None
            else ""
        )
        category_str = lead.category.value if lead.category else "—"
        return (
            f"🆕 <b>Yangi lid keldi!</b>\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 {lead.name}\n"
            f"📱 {lead.phone}\n"
            f"📍 {lead.district}\n"
            f"🏷 {category_str}{dims}{temp_tag}{conf_tag}\n\n"
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

    async def notify_measurement_lead(
        self,
        lead: "Lead",
        *,
        time_pref: str | None,
        dimensions: str | None,
        lead_temperature: str | None,
        closing_confidence: float | None,
        chat_type: str,
        chat_id: int,
        tg_user_id: int,
        username: str | None,
    ) -> None:
        """Send a measurement-lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        conf_str = f"{closing_confidence:.0%}" if closing_confidence is not None else "—"
        uname_str = f"@{username}" if username else "—"
        time_str = time_pref or "Ko'rsatilmagan"

        text = (
            f"📐 <b>Bepul o'lchov so'rovi!</b>\n\n"
            f"📋 Lid #{lead.id}\n"
            f"👤 Ism: {lead.name}\n"
            f"📱 Telefon: {lead.phone}\n"
            f"📍 Manzil: {lead.district}\n"
            f"🕐 Vaqt: {time_str}\n"
            f"📐 O'lcham: {dimensions or '—'}\n"
            f"🌡 Holat: {lead_temperature or '—'}\n"
            f"💡 Ishonch: {conf_str}\n\n"
            f"🔗 {chat_type} | {uname_str} | /lead_{lead.id}"
        )
        keyboard = self._lead_status_keyboard(lead.id)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, keyboard)
            await self._log_new_lead_action(lead.id)
        except Exception:
            log.exception("notify_measurement_lead_error", lead_id=lead.id)
        finally:
            await bot.session.close()

    async def notify_draft_lead(
        self,
        *,
        phone: str,
        name: str | None,
        username: str | None,
        user_id: int | None,
        chat_type: str,
        chat_id: int,
    ) -> None:
        """Send a draft phone-capture alert to admin DM only. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        uname_str = f"@{username}" if username else "—"
        name_str = name or "Noma'lum"
        uid_str = str(user_id) if user_id else "—"

        text = (
            f"📞 <b>Telefon raqam aniqlandi!</b>\n\n"
            f"📱 {phone}\n"
            f"👤 {name_str}\n"
            f"🔗 {uname_str} | #{uid_str} | {chat_type}"
        )

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await bot.send_message(self._admin_user_id, text)
        except Exception as exc:
            log.warning("notify_draft_lead_failed", error=str(exc))
        finally:
            await bot.session.close()

    # Shared score badges used by several notification methods
    _SCORE_BADGES: dict[str, str] = {
        "hot":  "🔥 HOT LEAD",
        "warm": "🟡 WARM LEAD",
        "cold": "⚪ COLD LEAD",
    }

    async def notify_ai_lead_collected(
        self,
        *,
        phone: str,
        district: str,
        area: float | None,
        room: str | None,
        name: str | None,
        username: str | None,
        user_id: int | None,
        score: str = "hot",
    ) -> None:
        """Send AI-collected lead card to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        badge = self._SCORE_BADGES.get(score, "🔥 HOT LEAD")
        name_str = name or "Noma'lum"
        lines = [f"<b>{badge}</b>\n", f"Ism: {name_str}"]
        if username:
            lines.append(f"Username: @{username}")
        elif user_id:
            lines.append(f"Telegram: <a href='tg://user?id={user_id}'>{user_id}</a>")
        if district:
            lines.append(f"Tuman: {district}")
        if area is not None:
            lines.append(f"Maydon: {area:g} m²")
        if room:
            lines.append(f"Xona: {room}")
        lines.append(f"Tel: {phone}")
        text = "\n".join(lines)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, None)
        except Exception as exc:
            log.warning("notify_ai_lead_failed", error=str(exc))
        finally:
            await bot.session.close()

    async def notify_lead_interest(
        self,
        *,
        score: str,
        name: str | None,
        username: str | None,
        user_id: int | None,
        topic: str,
    ) -> None:
        """Send a WARM/COLD interest signal to admin DM + all admin groups. Never raises."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        badge = self._SCORE_BADGES.get(score, "🟡 WARM LEAD")
        lines = [f"<b>{badge}</b>\n"]
        if name:
            lines.append(f"Ism: {name}")
        if username:
            lines.append(f"Username: @{username}")
        elif user_id:
            lines.append(f"Telegram: <a href='tg://user?id={user_id}'>{user_id}</a>")
        lines.append(f"Savol: {topic}")
        text = "\n".join(lines)

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await self._send_to_groups_and_dm(bot, text, None)
        except Exception as exc:
            log.warning("notify_lead_interest_failed", error=str(exc))
        finally:
            await bot.session.close()

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
