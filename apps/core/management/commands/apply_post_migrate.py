"""Apply post-migrate SQL: gold matviews, partial indexes that depend on data, etc.

Runs the .sql files under `infra/postgres/post_migrate/` in lexical order.
Idempotent — every CREATE uses IF NOT EXISTS.

Also bootstraps required extensions + `gold` schema if they are missing
(needed on managed Postgres providers like Railway/Render where the
container init scripts under `infra/postgres/init/` are not executed).

Usage:
    python manage.py apply_post_migrate
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


BOOTSTRAP_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE SCHEMA IF NOT EXISTS gold;
"""


class Command(BaseCommand):
    help = "Apply gold matviews and post-migrate SQL artefacts."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            self.stdout.write("==> Bootstrapping extensions + gold schema")
            cursor.execute(BOOTSTRAP_SQL)

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
                try:
                    cursor.execute(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"   FAILED {path.name}: {exc}"))
                    raise

        self.stdout.write(self.style.SUCCESS(f"Applied {len(files)} files."))
