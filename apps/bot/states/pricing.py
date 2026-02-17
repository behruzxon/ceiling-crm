"""FSM states for the pricing calculator conversation."""
from aiogram.fsm.state import State, StatesGroup


class PricingStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_length   = State()
    waiting_for_width    = State()
    waiting_for_addons   = State()
    waiting_for_district = State()
    confirming_quote     = State()
