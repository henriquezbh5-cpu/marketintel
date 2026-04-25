"""Bulk upsert helpers for time-series writes.

Hot path. Writes happen in 1K-row batches via psycopg's `execute_values`-style
COPY-or-multi-row insert. We use Django's `bulk_create(..., update_conflicts=True)`
which compiles to `INSERT ... ON CONFLICT (...) DO UPDATE ...` on Postgres.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction

from apps.instruments.models import Instrument, Source

from .models import PriceCandle, PriceSpot

logger = logging.getLogger(__name__)

BATCH_SIZE = 1_000


@dataclass(frozen=True)
class CandleRecord:
    instrument_id: int
    source_id: int
    resolution: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def upsert_candles(records: Iterable[CandleRecord], run_id: str = "") -> int:
    """Bulk upsert candles. Idempotent on natural key (instrument, ts, resolution, source).

    Returns the number of rows passed in. Conflict handling is `DO UPDATE` so
    re-running an ingest for an overlapping window simply refreshes prices —
    important when the upstream provider revises a recent candle (it happens).
    """
    objs = [
        PriceCandle(
            instrument_id=r.instrument_id,
            source_id=r.source_id,
            resolution=r.resolution,
            ts=r.ts,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
            run_id=run_id,
        )
        for r in records
    ]

    if not objs:
        return 0

    with transaction.atomic():
        PriceCandle.objects.bulk_create(
            objs,
            batch_size=BATCH_SIZE,
            update_conflicts=True,
            update_fields=["open", "high", "low", "close", "volume", "run_id"],
            unique_fields=["instrument", "source", "resolution", "ts"],
        )
    logger.info(
        "candles_upserted",
        extra={"count": len(objs), "run_id": run_id},
    )
    return len(objs)


def update_spot(
    instrument: Instrument,
    source: Source,
    price: Decimal,
    ts: datetime,
    change_24h_pct: Decimal | None = None,
    volume_24h: Decimal = Decimal("0"),
) -> None:
    """Upsert latest spot for an instrument. One row per instrument."""
    PriceSpot.objects.update_or_create(
        instrument=instrument,
        defaults={
            "source": source,
            "price": price,
            "ts": ts,
            "change_24h_pct": change_24h_pct,
            "volume_24h": volume_24h,
        },
    )
