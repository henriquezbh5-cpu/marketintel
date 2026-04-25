"""Ingestion tasks. Each task: fetch upstream → write to bronze → upsert to silver.

The bronze write is best-effort logging for debugging / replay; if it fails the
task still proceeds (the upstream payload is still represented in silver).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from django.conf import settings
from django.utils import timezone as djtz

from apps.instruments.models import Instrument, Source
from apps.instruments.services import InstrumentVersion, upsert_instrument_scd2
from apps.news.services import ArticleRecord, upsert_articles
from apps.prices.services import CandleRecord, update_spot, upsert_candles
from pipelines.connectors import (
    BinanceConnector,
    CoinGeckoConnector,
    CryptoPanicConnector,
)

from .common import pipeline_task

# ─── Catalog / instruments ────────────────────────────────────


@pipeline_task(queue="ingest")
def sync_coingecko_catalog(self, *, _run_id: str = "") -> int:
    """Refresh CoinGecko's coin list. SCD2-aware. Runs daily."""
    cg = CoinGeckoConnector.from_settings()
    coins = cg.list_coins()
    now = datetime.now(tz=timezone.utc)
    count = 0
    for coin in coins:
        upsert_instrument_scd2(
            InstrumentVersion(
                source_code="coingecko",
                external_id=coin.coin_id,
                symbol=coin.symbol,
                name=coin.name,
                asset_class="crypto",
                quote_currency="USD",
                metadata={"market_cap_rank": coin.market_cap_rank},
                observed_at=now,
            )
        )
        count += 1
    return count


# ─── Spot prices ──────────────────────────────────────────────


@pipeline_task(queue="ingest")
def ingest_prices_for_active_instruments(self, *, _run_id: str = "") -> int:
    """Fan-out over batches of CoinGecko ids. Called by Beat every minute."""
    coin_ids = list(
        Instrument.objects.filter(source__code="coingecko", is_current=True)
        .values_list("external_id", flat=True)[:250]
    )
    if not coin_ids:
        return 0

    # Batch within CoinGecko's per-call cap (~250 ids).
    return ingest_coingecko_spot_batch(coin_ids, _run_id=_run_id)


@pipeline_task(queue="ingest")
def ingest_coingecko_spot_batch(self, coin_ids: list[str], *, _run_id: str = "") -> int:
    cg = CoinGeckoConnector.from_settings()
    snapshots = cg.fetch_spot(coin_ids)

    cg_source = Source.objects.get(code="coingecko")
    instruments_by_id = {
        i.external_id: i
        for i in Instrument.objects.filter(
            source=cg_source, is_current=True, external_id__in=coin_ids,
        )
    }

    written = 0
    for snap in snapshots:
        instrument = instruments_by_id.get(snap.coin_id)
        if not instrument:
            continue
        update_spot(
            instrument=instrument,
            source=cg_source,
            price=snap.price_usd,
            ts=snap.ts,
            change_24h_pct=snap.change_24h_pct,
            volume_24h=snap.volume_24h,
        )
        written += 1
    return written


# ─── Candles ──────────────────────────────────────────────────


@pipeline_task(queue="ingest")
def ingest_binance_klines(
    self,
    symbol: str,
    resolution: str = "1m",
    limit: int = 500,
    *,
    _run_id: str = "",
) -> int:
    """Pull OHLCV klines and upsert into the partitioned fact table.

    Idempotent: PriceCandle's natural key dedupes overlapping ranges.
    """
    binance = BinanceConnector.from_settings()
    candles = binance.fetch_klines(symbol=symbol, interval=resolution, limit=limit)
    if not candles:
        return 0

    bn_source = Source.objects.get(code="binance")
    # Map Binance symbol (e.g. BTCUSDT) → instrument by symbol prefix
    base_symbol = symbol.replace("USDT", "")
    instrument = (
        Instrument.objects
        .filter(symbol=base_symbol, is_current=True, source__code="coingecko")
        .first()
    )
    if instrument is None:
        return 0

    records = [
        CandleRecord(
            instrument_id=instrument.pk,
            source_id=bn_source.pk,
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


# ─── News ─────────────────────────────────────────────────────


@pipeline_task(queue="ingest")
def ingest_news_recent(self, currencies: tuple[str, ...] = (), *, _run_id: str = "") -> int:
    from django.conf import settings
    if not settings.CRYPTOPANIC_API_KEY:
        # Endpoint requires auth even for "public" feed since their 2024 change.
        # Don't burn retries — log and skip.
        return 0

    cp = CryptoPanicConnector.from_settings()
    articles = cp.fetch_recent(currencies=currencies)

    records = [
        ArticleRecord(
            source_code="cryptopanic",
            external_id=a.external_id,
            title=a.title,
            url=a.url,
            summary="",
            published_at=a.published_at,
            sentiment=a.sentiment,
            sentiment_score=None,
            metadata={"source_name": a.source_name},
            mentioned_symbols=a.currencies,
        )
        for a in articles
    ]
    return upsert_articles(records)
