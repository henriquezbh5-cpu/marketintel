"""Time-series price facts.

The physical table is created as a Postgres declarative-partitioned parent
(see `infra/postgres/init/02_partitions.sql`), partitioned by RANGE on `ts`.
Django's ORM treats it as a single table; partition pruning happens in the DB
when queries include `ts` in WHERE.

Index strategy:
  - BRIN on (ts) — append-only time-series, BRIN is ~100x cheaper than B-tree.
  - B-tree on (instrument_id, ts DESC) — typical query: latest N candles per symbol.
  - Partial unique on (instrument_id, ts, source_id) — dedup natural key.
"""
from __future__ import annotations

from django.db import models

from apps.instruments.models import Instrument, Source


class Resolution(models.TextChoices):
    M1 = "1m", "1 minute"
    M5 = "5m", "5 minutes"
    M15 = "15m", "15 minutes"
    H1 = "1h", "1 hour"
    H4 = "4h", "4 hours"
    D1 = "1d", "1 day"


class PriceCandle(models.Model):
    """OHLCV candle. One row per (instrument, source, resolution, ts)."""

    instrument = models.ForeignKey(
        Instrument, on_delete=models.PROTECT, related_name="candles", db_index=False,
    )
    source = models.ForeignKey(Source, on_delete=models.PROTECT, db_index=False)
    resolution = models.CharField(max_length=8, choices=Resolution.choices, db_index=False)
    ts = models.DateTimeField(help_text="Candle open time, UTC")

    open = models.DecimalField(max_digits=24, decimal_places=12)
    high = models.DecimalField(max_digits=24, decimal_places=12)
    low = models.DecimalField(max_digits=24, decimal_places=12)
    close = models.DecimalField(max_digits=24, decimal_places=12)
    volume = models.DecimalField(max_digits=32, decimal_places=12, default=0)

    ingested_at = models.DateTimeField(auto_now_add=True)
    run_id = models.CharField(
        max_length=64, blank=True,
        help_text="Dagster run id that produced this row (for lineage)",
    )

    class Meta:
        # Partitioning + indexes are managed by hand-rolled migrations; we
        # don't declare a unique_together because Django would try to enforce
        # it via a regular UNIQUE which won't include the partition key.
        # See infra/postgres/init/02_partitions.sql for the actual DDL.
        db_table = "fact_price_candle"
        managed = True  # Django manages the parent; partitions managed externally
        indexes = [
            # Composite for "give me last N candles for symbol X"
            models.Index(fields=["instrument", "-ts"], name="ix_price_inst_ts_desc"),
            models.Index(fields=["resolution", "ts"], name="ix_price_resolution_ts"),
        ]

    def __str__(self) -> str:
        return f"{self.instrument.symbol} @ {self.ts.isoformat()} ({self.resolution})"


class PriceSpot(models.Model):
    """Latest spot price per instrument. Tiny table, served from Redis cache.

    This is a denormalised view kept up-to-date by the price-spot Celery task.
    """

    instrument = models.OneToOneField(
        Instrument, on_delete=models.CASCADE, primary_key=True, related_name="spot",
    )
    price = models.DecimalField(max_digits=24, decimal_places=12)
    change_24h_pct = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    volume_24h = models.DecimalField(max_digits=32, decimal_places=12, default=0)
    ts = models.DateTimeField()
    source = models.ForeignKey(Source, on_delete=models.PROTECT)

    class Meta:
        db_table = "fact_price_spot"
        indexes = [
            models.Index(fields=["-ts"], name="ix_spot_ts_desc"),
        ]
