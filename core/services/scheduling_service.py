"""
SchedulingService — appointment creation and installer assignment.
"""
from __future__ import annotations
from datetime import datetime
from core.domain.appointment import Appointment
from core.repositories.appointment_repo import AbstractAppointmentRepository
from shared.constants.enums import AppointmentType
from shared.logging import get_logger

log = get_logger(__name__)


class SchedulingService:
    """
    Manages measurement and installation appointment booking.
    Assigns installers based on district match and availability.
    """

    def __init__(self, appointment_repo: AbstractAppointmentRepository) -> None:
        self._repo = appointment_repo

    async def book_appointment(
        self,
        lead_id: int,
        appt_type: AppointmentType,
        scheduled_at: datetime,
        district: str,
        created_by: int,
        address: str | None = None,
        notes: str | None = None,
    ) -> Appointment:
        """Create appointment and auto-assign best available installer. TODO: implement."""
        raise NotImplementedError

    async def assign_installer(
        self, appointment_id: int, installer_id: int, actor_id: int
    ) -> Appointment:
        """Manually assign an installer. TODO: implement."""
        raise NotImplementedError

    async def complete_appointment(self, appointment_id: int, actor_id: int) -> Appointment:
        """Mark appointment as DONE; may trigger pipeline auto-advance. TODO: implement."""
        raise NotImplementedError

    async def find_available_installers(
        self, district: str, scheduled_at: datetime, appt_type: AppointmentType
    ) -> list[object]:
        """Return available installers ranked by district fit. TODO: implement."""
        raise NotImplementedError
