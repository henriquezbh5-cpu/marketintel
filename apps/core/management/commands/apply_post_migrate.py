"""Apply post-migrate SQL: gold matviews, partial indexes that depend on data, etc.

Runs the .sql files under `infra/postgres/post_migrate/` in lexical order.
Idempotent — every CREATE uses IF NOT EXISTS.

Usage:
    python manage.py apply_post_migrate
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Apply gold matviews and post-migrate SQL artefacts."

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR) / "infra" / "postgres" / "post_migrate"
        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f"Not found: {root}"))
            return

        files = sorted(root.glob("*.sql"))
        if not files:
            self.stdout.write(self.style.WARNING("No .sql files found"))
            return

        with connection.cursor() as cursor:
            for path in files:
                self.stdout.write(f"==> Applying {path.name}")
                cursor.execute(path.read_text(encoding="utf-8"))

        self.stdout.write(self.style.SUCCESS(f"Applied {len(files)} files."))
