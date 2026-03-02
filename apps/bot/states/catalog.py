"""FSM states for the catalog browsing flow."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CatalogStates(StatesGroup):
    waiting_for_design = State()
