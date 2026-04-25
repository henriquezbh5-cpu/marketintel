"""Abstract base models + DLQ table.

`TimestampedModel` and `SCD2Model` are abstract — subclassed elsewhere.
`DeadLetterTask` is a concrete model used by the Celery task base to record
terminally-failed jobs for human inspection / requeue.
"""
from __future__ import annotations

from django.db import models


class TimestampedModel(models.Model):
    """Adds created_at / updated_at to any concrete subclass."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SCD2Model(TimestampedModel):
    """Slowly Changing Dimension type 2.

    Subclasses must define a `natural_key()` returning a tuple. We store one
    row per (natural_key, valid_from) pair; `is_current` distinguishes the
    active version. The service layer owns transition logic.
    """

    valid_from = models.DateTimeField(db_index=True)
    valid_to = models.DateTimeField(null=True, blank=True, db_index=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def natural_key(self) -> tuple:  # pragma: no cover - abstract
        raise NotImplementedError


class DeadLetterTask(models.Model):
    """Terminally-failed Celery jobs.

    Inserted by `IdempotentTask.on_failure`. Operators inspect via admin or
    `python manage.py dlq_list/requeue` and can re-enqueue once the underlying
    cause is fixed. Idempotency on the tasks themselves makes requeue safe.
    """

    task_id = models.CharField(max_length=64, unique=True)
    task_name = models.CharField(max_length=255, db_index=True)
    queue = models.CharField(max_length=64, blank=True, db_index=True)
    args = models.JSONField(default=list)
    kwargs = models.JSONField(default=dict)
    exception = models.TextField()
    traceback = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    requeued_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_dead_letter_task"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.task_name} {self.task_id}"
