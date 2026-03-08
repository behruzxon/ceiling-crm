"""FSM states for the tenant menu builder."""
from aiogram.fsm.state import State, StatesGroup


class MenuBuilderStates(StatesGroup):
    viewing = State()
    add_button_text = State()
    add_button_type = State()
    add_button_action = State()
    add_button_response = State()
    add_button_row = State()
    edit_select = State()
    edit_field = State()
    edit_value = State()
    delete_select = State()
    delete_confirm = State()
    reorder_select = State()
    reorder_direction = State()
