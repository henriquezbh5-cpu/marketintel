"""Dagster code location.

Loaded by `dagster dev -m pipelines.orchestration`. Exports the `Definitions`
object that Dagster discovers — it bundles assets, jobs, schedules, sensors.
"""
from __future__ import annotations

import os

import django

# Initialise Django before importing anything that touches the ORM. Dagster
# loads this module standalone, so settings are not yet wired.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from dagster import Definitions, ScheduleDefinition  # noqa: E402

from .assets import (  # noqa: E402
    bronze_coingecko_spot,
    bronze_news_recent,
    silver_news_articles,
    silver_price_candles,
    silver_price_spot,
)
from .jobs import full_refresh_job, ingest_prices_job  # noqa: E402
from .sensors import partition_sensor  # noqa: E402

defs = Definitions(
    assets=[
        bronze_coingecko_spot,
        silver_price_spot,
        silver_price_candles,
        bronze_news_recent,
        silver_news_articles,
    ],
    jobs=[ingest_prices_job, full_refresh_job],
    schedules=[
        ScheduleDefinition(
            name="every_minute_prices",
            cron_schedule="* * * * *",
            job=ingest_prices_job,
        ),
    ],
    sensors=[partition_sensor],
)
