"""Shared decorators / helpers for all Celery tasks.

A task in this project is:
  - Idempotent (re-running with same args is safe)
  - Retried with exponential backoff + jitter on transient failures
  - Time-bounded (soft limit < hard limit)
  - Sent to DLQ if retries exhaust
  - Observable (structured logs with task_id + business keys)
"""
from __future__ import annotations

import functools
import logging
import uuid
from collections.abc import Callable
from typing import Any

from celery import Task, shared_task
from httpx import HTTPError

from pipelines.connectors.base import ConnectorError, RateLimited

logger = logging.getLogger(__name__)


class IdempotentTask(Task):
    """Base task class with sensible defaults for our pipelines."""

    autoretry_for = (HTTPError, ConnectorError, RateLimited)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5
    acks_late = True
    track_started = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Persist terminally-failed jobs to the DLQ table + structured log."""
        logger.error(
            "task_dead_lettered",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "exception": str(exc),
            },
        )
        try:
            # Late import to avoid Celery autodiscovery at module load.
            from apps.core.metrics import dlq_inserts_total
            from apps.core.models import DeadLetterTask

            dlq_inserts_total.labels(task_name=self.name).inc()

            DeadLetterTask.objects.update_or_create(
                task_id=task_id,
                defaults={
                    "task_name": self.name,
                    "queue": (self.request.delivery_info or {}).get("routing_key", ""),
                    "args": list(args or []),
                    "kwargs": dict(kwargs or {}),
                    "exception": repr(exc)[:8192],
                    "traceback": str(einfo)[:16384] if einfo else "",
                    "attempts": self.request.retries + 1,
                },
            )
        except Exception:  # noqa: BLE001 — DLQ write must never mask the real failure
            logger.exception("dlq_write_failed", extra={"task_id": task_id})

        super().on_failure(exc, task_id, args, kwargs, einfo)


def pipeline_task(*, queue: str = "default", **task_kwargs):
    """Decorator wrapping `shared_task` with our defaults."""

    def decorator(fn: Callable[..., Any]):
        bound_kwargs = {
            "base": IdempotentTask,
            "queue": queue,
            "bind": True,
            **task_kwargs,
        }

        @shared_task(**bound_kwargs)
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            run_id = kwargs.pop("_run_id", None) or uuid.uuid4().hex[:12]
            log = logger.bind() if hasattr(logger, "bind") else logger
            try:
                log.info(
                    "task_start",
                    extra={
                        "task_id": self.request.id,
                        "task_name": self.name,
                        "run_id": run_id,
                        "kwargs": kwargs,
                    },
                )
                result = fn(self, *args, _run_id=run_id, **kwargs)
                log.info(
                    "task_done",
                    extra={
                        "task_id": self.request.id,
                        "task_name": self.name,
                        "run_id": run_id,
                    },
                )
                return result
            except Exception:
                log.exception(
                    "task_error",
                    extra={
                        "task_id": self.request.id,
                        "task_name": self.name,
                        "run_id": run_id,
                    },
                )
                raise

        return wrapper

    return decorator
