"""FSM states for pipeline stage management."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class PipelineStates(StatesGroup):
    waiting_lost_reason = State()  # admin typed "Boshqa..." — waiting for reason text
