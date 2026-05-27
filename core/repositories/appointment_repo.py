"""Appointment repository interface."""

from __future__ import annotations

from abc import abstractmethod
from datetime import date

from core.domain.appointment import Appointment
from core.repositories.base import BaseRepository
from shared.constants.enums import AppointmentType


class AbstractAppointmentRepository(BaseRepository[Appointment, int]):
    """Contract for appointment persistence."""

    @abstractmethod
    async def get_by_installer(
        self, installer_id: int, date_from: date, date_to: date
    ) -> list[Appointment]: ...

    @abstractmethod
    async def get_upcoming(self, hours_ahead: int = 2) -> list[Appointment]: ...

    @abstractmethod
    async def get_by_district_and_date(
        self, district: str, target_date: date, appt_type: AppointmentType
    ) -> list[Appointment]: ...
