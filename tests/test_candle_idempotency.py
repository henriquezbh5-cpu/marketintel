"""Bulk upsert of candles must be idempotent on the natural key."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.prices.models import PriceCandle
from apps.prices.services import CandleRecord, upsert_candles


def _make_record(instrument, source, ts, close):
    return CandleRecord(
        instrument_id=instrument.pk,
        source_id=source.pk,
        resolution="1m",
        ts=ts,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("1.0"),
    )


@pytest.mark.integration
def test_double_insert_is_idempotent(btc_instrument, coingecko_source):
    ts = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    record = _make_record(btc_instrument, coingecko_source, ts, "60000")

    upsert_candles([record])
    upsert_candles([record])

    assert PriceCandle.objects.count() == 1


@pytest.mark.integration
def test_overlap_updates_in_place(btc_instrument, coingecko_source):
    ts = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)

    upsert_candles([_make_record(btc_instrument, coingecko_source, ts, "60000")])
    upsert_candles([_make_record(btc_instrument, coingecko_source, ts, "60500")])

    candle = PriceCandle.objects.get()
    assert candle.close == Decimal("60500")
