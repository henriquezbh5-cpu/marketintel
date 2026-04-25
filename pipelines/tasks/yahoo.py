"""Yahoo Finance ingestion tasks (equities — stocks, indices, ETFs)."""
from __future__ import annotations

from decimal import Decimal

from apps.instruments.models import Instrument, Source
from apps.prices.services import CandleRecord, update_spot, upsert_candles
from pipelines.connectors import YahooFinanceConnector

from .common import pipeline_task


@pipeline_task(queue="ingest")
def ingest_yahoo_spot_for_active(self, *, _run_id: str = "") -> int:
    """Refresh quote for every Yahoo-tracked instrument. Called by Beat."""
    yahoo = YahooFinanceConnector.from_settings()
    yf_source = Source.objects.get(code="yahoo_finance")

    updated = 0
    for inst in Instrument.objects.filter(source=yf_source, is_current=True):
        try:
            quote = yahoo.fetch_quote(inst.external_id)
        except Exception:  # noqa: BLE001 — log + skip; per-symbol failure shouldn't kill the batch
            continue
        if quote is None or quote.price == 0:
            continue
        update_spot(
            instrument=inst,
            source=yf_source,
            price=quote.price,
            ts=quote.ts,
            change_24h_pct=quote.change_pct,
            volume_24h=quote.volume,
        )
        updated += 1
    return updated


@pipeline_task(queue="ingest")
def ingest_yahoo_candles(
    self,
    symbol: str,
    resolution: str = "1m",
    range_: str | None = None,
    *,
    _run_id: str = "",
) -> int:
    """Pull OHLCV bars for a symbol and upsert into the partitioned fact table."""
    yahoo = YahooFinanceConnector.from_settings()
    quote, candles = yahoo.fetch_chart(symbol, resolution=resolution, range_=range_)
    if not candles:
        return 0

    yf_source = Source.objects.get(code="yahoo_finance")
    instrument = (
        Instrument.objects
        .filter(external_id__iexact=symbol, source=yf_source, is_current=True)
        .first()
    )
    if instrument is None:
        return 0

    # Refresh spot in the same call — it's free.
    if quote is not None and quote.price:
        update_spot(
            instrument=instrument, source=yf_source,
            price=quote.price, ts=quote.ts,
            change_24h_pct=quote.change_pct, volume_24h=quote.volume,
        )

    records = [
        CandleRecord(
            instrument_id=instrument.pk,
            source_id=yf_source.pk,
            resolution=resolution,
            ts=c.open_time,
            open=Decimal(c.open),
            high=Decimal(c.high),
            low=Decimal(c.low),
            close=Decimal(c.close),
            volume=Decimal(c.volume),
        )
        for c in candles
    ]
    return upsert_candles(records, run_id=_run_id)
