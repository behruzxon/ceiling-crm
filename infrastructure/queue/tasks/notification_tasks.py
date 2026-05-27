"""Celery tasks for async notifications."""
from __future__ import annotations

from infrastructure.queue.app import celery_app


@celery_app.task
def send_lead_card_async(lead_id: int) -> None:
    """Send lead card to admin group asynchronously. TODO: implement."""
    raise NotImplementedError


@celery_app.task
def send_appointment_reminder_async(appointment_id: int) -> None:
    """Send appointment reminder. TODO: implement."""
    raise NotImplementedError
