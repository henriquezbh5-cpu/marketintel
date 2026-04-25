"""Dagster sensors. Fire jobs in response to external state changes.

`partition_sensor`: watches the calendar; when month-end approaches it triggers
the maintenance task that creates the next monthly partition on the candle table.
This decouples partition creation from beat schedules — sensors give us
exactly-once semantics via cursors.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from dagster import (
    DefaultSensorStatus,
    RunRequest,
    SensorEvaluationContext,
    SkipReason,
    define_asset_job,
    sensor,
)

# We define a tiny job that wraps the maintenance task as a Dagster op.
# Defined locally to avoid circular imports.
_partition_job = define_asset_job(
    name="ensure_partitions_job",
    selection="silver_price_candles",
)


@sensor(
    job=_partition_job,
    minimum_interval_seconds=3600,  # check hourly
    default_status=DefaultSensorStatus.RUNNING,
)
def partition_sensor(context: SensorEvaluationContext):
    """Trigger partition creation in the last 5 days of the month.

    Cursor stores the last (year, month) we acted on so we don't double-fire.
    """
    today = date.today()
    days_left = (_next_month(today) - today).days
    if days_left > 5:
        return SkipReason("more than 5 days to month end")

    cursor_key = today.strftime("%Y-%m")
    if context.cursor == cursor_key:
        return SkipReason("already triggered for this month")

    context.update_cursor(cursor_key)
    return RunRequest(
        run_key=f"partitions-{cursor_key}",
        tags={"source": "partition_sensor", "iso_date": datetime.now(tz=timezone.utc).isoformat()},
    )


def _next_month(d: date) -> date:
    first = d.replace(day=1)
    return (first + timedelta(days=32)).replace(day=1)
