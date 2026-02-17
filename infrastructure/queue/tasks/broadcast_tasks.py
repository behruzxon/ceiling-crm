"""Celery tasks for broadcast message delivery."""
from __future__ import annotations
from infrastructure.queue.app import celery_app
from shared.logging import get_logger

log = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_broadcast_message(self, user_id: int, broadcast_id: int, message: str) -> dict:
    """
    Send a single broadcast message to one user.
    Rate limited to 30/sec by Celery config.
    TODO: implement with aiogram Bot.send_message.
    """
    raise NotImplementedError


@celery_app.task
def process_broadcast_batch(broadcast_id: int) -> dict:
    """
    Process a full broadcast: resolve audience, enqueue individual tasks.
    TODO: implement batch processing with progress tracking.
    """
    raise NotImplementedError
