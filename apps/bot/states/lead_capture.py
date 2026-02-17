"""FSM states for the lead capture conversation."""
from aiogram.fsm.state import State, StatesGroup


class LeadCaptureStates(StatesGroup):
    waiting_for_name     = State()
    waiting_for_phone    = State()
    waiting_for_district = State()
    waiting_for_notes    = State()
    confirming_lead      = State()
