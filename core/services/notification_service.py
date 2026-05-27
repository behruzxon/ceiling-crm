"""
NotificationService — sends Telegram notifications to users and admins.
Decoupled from handlers; called by services and event handlers.
"""
from __future__ import annotations

from core.domain.appointment import Appointment
from core.domain.lead import Lead
from shared.logging import get_logger

log = get_logger(__name__)


class NotificationService:
    """
    Sends formatted Telegram messages.
    Bot instance is injected at startup.
    All message templates use i18n.
    """

    def __init__(self, bot: object) -> None:
        self._bot = bot

    async def send_lead_card_to_admin(self, lead: Lead) -> None:
        """Send formatted lead card with action buttons to admin group. TODO: implement."""
        raise NotImplementedError

    async def send_lead_confirmation_to_client(self, lead: Lead) -> None:
        """Confirm lead submission to client. TODO: implement."""
        raise NotImplementedError

    async def send_appointment_reminder(self, appointment: Appointment) -> None:
        """Send reminder to client and installer 2h before appointment. TODO: implement."""
        raise NotImplementedError

    async def send_stage_change_notification(
        self, lead: Lead, old_stage: str, new_stage: str
    ) -> None:
        """Notify client of pipeline stage change. TODO: implement."""
        raise NotImplementedError
