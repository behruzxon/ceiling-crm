"""Celery application factory."""
from __future__ import annotations
from celery import Celery
from shared.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "ceiling_crm",
        broker=settings.redis.celery_url,
        backend=settings.redis.celery_url,
        include=[
            "infrastructure.queue.tasks.broadcast_tasks",
            "infrastructure.queue.tasks.notification_tasks",
            "infrastructure.queue.tasks.export_tasks",
            "infrastructure.queue.tasks.package_tasks",
        ],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Tashkent",
        enable_utc=True,
        worker_max_tasks_per_child=1000,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Rate limit: 30 broadcast messages per second (Telegram API limit)
        task_default_rate_limit="30/s",
    )
    return app


celery_app = create_celery_app()
