"""FSM states for appointment booking."""
from aiogram.fsm.state import State, StatesGroup


class AppointmentStates(StatesGroup):
    waiting_for_date     = State()
    waiting_for_time     = State()
    waiting_for_address  = State()
    confirming_booking   = State()
