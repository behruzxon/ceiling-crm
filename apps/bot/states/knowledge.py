"""FSM states for the AI Knowledge Base manager."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class KnowledgeAddStates(StatesGroup):
    """Add a new knowledge entry: category → title → content."""
    waiting_category = State()
    waiting_title = State()
    waiting_content = State()


class KnowledgeEditStates(StatesGroup):
    """Edit an existing entry: choose field → enter new value."""
    waiting_field = State()
    waiting_value = State()
