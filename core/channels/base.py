"""
core.channels.base
~~~~~~~~~~~~~~~~~~
ChannelDelivery abstraction for sending messages over any channel
(Telegram, web chat, SMS, etc.) without depending on aiogram or any
specific transport library.

Implementing classes live in the respective application layer:
  - apps.bot.channels.telegram_delivery.TelegramChannelDelivery
  - (future) apps.web.channels.websocket_delivery.WebSocketChannelDelivery
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ChannelDelivery(ABC):
    """Abstract message delivery channel.

    All methods are fire-and-forget: they must catch their own exceptions
    and never propagate them to callers.
    """

    @abstractmethod
    async def send_text(self, user_id: str, text: str) -> None:
        """Send a plain text message to a user."""

    @abstractmethod
    async def send_typing(self, user_id: str) -> None:
        """Send a typing indicator (no-op on channels that don't support it)."""

    @abstractmethod
    async def request_phone(self, user_id: str) -> None:
        """Request the user's phone number (no-op on channels that don't support it)."""

    @abstractmethod
    async def send_admin_notification(
        self,
        text: str,
        *,
        lead_id: int | None = None,
    ) -> None:
        """Send a notification to the admin channel.

        Args:
            text: HTML-formatted notification text.
            lead_id: When provided, the channel may attach action buttons
                     (e.g. Telegram inline keyboard) for quick lead management.
        """
