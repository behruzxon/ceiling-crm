"""Celery tasks for data export operations."""
from __future__ import annotations
from infrastructure.queue.app import celery_app


@celery_app.task
def sync_leads_to_sheets(sheet_id: str) -> dict:
    """Sync lead delta to Google Sheets. TODO: implement."""
    raise NotImplementedError


@celery_app.task
def generate_monthly_report(month: int, year: int, recipient_id: int) -> dict:
    """Generate PDF report and send to admin. TODO: implement."""
    raise NotImplementedError
