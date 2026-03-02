"""FSM states for the measurement lead capture flow."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class MeasurementLeadStates(StatesGroup):
    waiting_for_name     = State()
    waiting_for_phone    = State()
    waiting_for_location = State()
    waiting_for_time     = State()
