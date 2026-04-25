"""Maintenance tasks.

`ensure_future_partitions`: make sure the next 3 monthly partitions exist on
the price candle parent. Runs on the 25th of every month — far enough ahead
that no insert ever lands without a target partition.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db import connection

from .common import pipeline_task


def _month_floor(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    return _month_floor(d + timedelta(days=32))


@pipeline_task(queue="default")
def ensure_future_partitions(self, months_ahead: int = 3, *, _run_id: str = "") -> int:
    """Idempotent: CREATE ... IF NOT EXISTS pattern via DO blocks."""
    today = date.today()
    created = 0
    cursor_month = _month_floor(today)
    with connection.cursor() as cursor:
        for _ in range(months_ahead + 1):
            start = cursor_month
            end = _add_month(start)
            partition_name = f"fact_price_candle_{start:%Y_%m}"
            sql = f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_class WHERE relname = '{partition_name}'
                ) THEN
                    EXECUTE format(
                        'CREATE TABLE %I PARTITION OF fact_price_candle FOR VALUES FROM (%L) TO (%L)',
                        '{partition_name}', '{start.isoformat()}', '{end.isoformat()}'
                    );
                END IF;
            END
            $$;
            """
            cursor.execute(sql)
            created += 1
            cursor_month = end
    return created
