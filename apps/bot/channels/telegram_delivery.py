"""
apps.bot.channels.telegram_delivery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Telegram implementation of ChannelDelivery.

Creates a short-lived Bot session per call (same pattern as the previous
LeadNotificationService) so no long-lived Bot instance is required.

Usage (wired in infrastructure/di.py)
--------------------------------------
  channel = TelegramChannelDelivery(
      bot_token=settings.bot.token.get_secret_value(),
      admin_group_id=settings.bot.admin_group_id,
  )
  service = LeadNotificationService(admin_user_id=..., channel=channel)
"""
from __future__ import annotations

from core.channels.base import ChannelDelivery
from shared.logging import get_logger

log = get_logger(__name__)


def build_lead_action_keyboard(lead_id: int) -> "InlineKeyboardMarkup":
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
                text="\u274c Yo'qotildi",
                callback_data=f"lead:{lead_id}:status:lost",
            ),
        ],
        [
            InlineKeyboardButton(
                text="\U0001f4a1 Operator yordam",
                callback_data=f"op:menu:{lead_id}",
            ),
        ],
    ])


class TelegramChannelDelivery(ChannelDelivery):
    """Delivers messages via the Telegram Bot API."""

    def __init__(self, bot_token: str, admin_group_id: int | None) -> None:
        self._bot_token = bot_token
        self._admin_group_id = admin_group_id

    async def send_text(self, user_id: str, text: str) -> None:
        """Send a plain text message to a Telegram user."""
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        try:
            await bot.send_message(int(user_id), text)
        except Exception as exc:
            log.warning("telegram_send_text_failed", user_id=user_id, error=str(exc))
        finally:
            await bot.session.close()

    async def send_typing(self, user_id: str) -> None:
        """Send a typing action to a Telegram user."""
        from aiogram import Bot

        bot = Bot(token=self._bot_token)
        try:
            await bot.send_chat_action(int(user_id), "typing")
        except Exception as exc:
            log.warning("telegram_send_typing_failed", user_id=user_id, error=str(exc))
        finally:
            await bot.session.close()

    async def request_phone(self, user_id: str) -> None:
        """Phone request is handled via FSM in aiogram handlers; not supported here."""
        log.debug("request_phone_not_supported_via_channel", user_id=user_id)

    async def send_admin_notification(
        self,
        text: str,
        *,
        lead_id: int | None = None,
    ) -> None:
        """Send notification text to the configured admin group.

        If *lead_id* is provided, attaches the lead quick-action keyboard.
        """
        if not self._admin_group_id:
            log.warning("admin_group_id_not_configured")
            return

        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        bot = Bot(
            token=self._bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        keyboard = build_lead_action_keyboard(lead_id) if lead_id else None
        try:
            await bot.send_message(self._admin_group_id, text, reply_markup=keyboard)
        except Exception as exc:
            log.warning("notify_group_failed", chat_id=self._admin_group_id, error=str(exc))
        finally:
            await bot.session.close()
