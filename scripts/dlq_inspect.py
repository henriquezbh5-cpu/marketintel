#!/usr/bin/env python
"""Inspect / requeue dead-lettered Celery tasks.

Run inside the web container:
    docker compose exec web python scripts/dlq_inspect.py list
    docker compose exec web python scripts/dlq_inspect.py requeue <task_id>
    docker compose exec web python scripts/dlq_inspect.py purge --older-than-days 30
"""
from __future__ import annotations

import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from datetime import timedelta  # noqa: E402

from celery import current_app  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.core.models import DeadLetterTask  # noqa: E402


def cmd_list(args):
    qs = DeadLetterTask.objects.filter(resolved_at__isnull=True)
    if args.task:
        qs = qs.filter(task_name__icontains=args.task)
    for dlq in qs[: args.limit]:
        print(
            f"{dlq.task_id}\t{dlq.task_name}\t"
            f"queue={dlq.queue}\tattempts={dlq.attempts}\t{dlq.created_at}"
        )
        print(f"  exception: {dlq.exception[:200]}")


def cmd_requeue(args):
    dlq = DeadLetterTask.objects.get(task_id=args.task_id)
    current_app.send_task(
        dlq.task_name, args=dlq.args, kwargs=dlq.kwargs, queue=dlq.queue or "default",
    )
    dlq.requeued_at = timezone.now()
    dlq.save(update_fields=["requeued_at"])
    print(f"Re-enqueued {dlq.task_name} ({dlq.task_id})")


def cmd_purge(args):
    cutoff = timezone.now() - timedelta(days=args.older_than_days)
    deleted, _ = DeadLetterTask.objects.filter(
        resolved_at__isnull=False, resolved_at__lt=cutoff,
    ).delete()
    print(f"Deleted {deleted} resolved DLQ rows older than {args.older_than_days}d")


def main():
    p = argparse.ArgumentParser(description="DLQ tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list")
    s.add_argument("--task", help="filter by task name substring")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("requeue")
    s.add_argument("task_id")
    s.set_defaults(func=cmd_requeue)

    s = sub.add_parser("purge")
    s.add_argument("--older-than-days", type=int, default=30)
    s.set_defaults(func=cmd_purge)

    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
