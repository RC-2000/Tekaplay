"""Celery application.

Queues: default (general), ai (LLM calls — slow, rate-limited), events
(analytics fan-out). Tasks must be idempotent: every retryable operation takes
an idempotency key and checks it before doing work.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    settings.app_name,
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.modules.ai.*": {"queue": "ai"},
        "app.modules.analytics.*": {"queue": "events"},
    },
)
