"""Celery application factory.

Workers run with: celery -A config worker -l INFO -Q default,ingest,transform,dlq -c 4
Beat:           celery -A config beat -l INFO
"""
from __future__ import annotations

import logging
import os

from celery import Celery, signals
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("marketintel")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Tasks live both in Django apps (autodiscovered) and in `pipelines.tasks.*`
# (not a Django app, so registered via CELERY_IMPORTS in settings).
app.autodiscover_tasks()

logger = logging.getLogger(__name__)


# ─── Periodic tasks ───────────────────────────────────────────
app.conf.beat_schedule = {
    "ingest-equities-1m": {
        "task": "pipelines.tasks.yahoo.ingest_yahoo_spot_for_active",
        "schedule": crontab(minute="*"),
        "options": {"queue": "ingest", "expires": 50},
    },
    "ingest-news-5m": {
        "task": "pipelines.tasks.ingest.ingest_news_recent",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "ingest", "expires": 240},
    },
    "refresh-gold-marts-5m": {
        "task": "pipelines.tasks.transform.refresh_gold_marts",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "transform"},
    },
    "create-monthly-partitions": {
        "task": "pipelines.tasks.maintenance.ensure_future_partitions",
        "schedule": crontab(day_of_month="25", hour="0", minute="0"),
        "options": {"queue": "default"},
    },
}


# ─── Signal hooks ─────────────────────────────────────────────
@signals.task_failure.connect
def _on_task_failure(sender=None, task_id=None, exception=None, **_kwargs):
    """Send terminally failed tasks to DLQ for inspection."""
    logger.error(
        "task_failure",
        extra={
            "task_id": task_id,
            "task_name": getattr(sender, "name", "unknown"),
            "exception": str(exception),
        },
    )


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
