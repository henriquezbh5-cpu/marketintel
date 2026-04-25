"""Dagster assets — declarative pipeline graph.

Each asset is a node in the lineage graph. Bronze assets pull raw upstream
data and dump JSONL to MinIO. Silver assets transform + load to Postgres.
Heavy paralelism is delegated to Celery tasks via `celery_executor` or via
explicit fan-out using a Celery `group()`.

Convention: bronze first, silver depends on bronze, gold depends on silver.

Note: this module deliberately avoids `from __future__ import annotations`.
Dagster inspects type hints at runtime to validate context parameters and
breaks when they are stringified.
"""
import uuid
from datetime import datetime, timezone

from dagster import (
    AssetExecutionContext,
    AssetIn,
    DailyPartitionsDefinition,
    MetadataValue,
    asset,
)

from apps.core.storage import put_jsonl_gz
from django.conf import settings
from pipelines.connectors import CoinGeckoConnector, CryptoPanicConnector

DAILY = DailyPartitionsDefinition(start_date="2024-01-01")


# ─── Bronze ───────────────────────────────────────────────────


@asset(
    description="Raw spot price snapshot from CoinGecko, dumped to bronze bucket.",
    compute_kind="python",
    group_name="bronze",
)
def bronze_coingecko_spot(context: AssetExecutionContext) -> dict:
    cg = CoinGeckoConnector.from_settings()
    # In production this would page through all instruments. For the scaffold
    # we pull the top-250 by market cap as a representative slice.
    coin_ids = [coin.coin_id for coin in cg.list_coins()[:250]]
    snapshots = cg.fetch_spot(coin_ids)

    run_id = context.run_id or uuid.uuid4().hex
    now = datetime.now(tz=timezone.utc)
    key = (
        f"coingecko/spot/dt={now:%Y-%m-%d}/hh={now:%H}/{run_id}.jsonl.gz"
    )
    count = put_jsonl_gz(
        bucket=settings.S3_BRONZE_BUCKET,
        key=key,
        records=({**s.raw, "_observed_at": s.ts.isoformat()} for s in snapshots),
    )
    context.add_output_metadata(
        {"records": count, "s3_key": MetadataValue.text(key)}
    )
    return {"key": key, "count": count, "run_id": run_id}


@asset(
    description="Raw news payloads from CryptoPanic public feed.",
    compute_kind="python",
    group_name="bronze",
)
def bronze_news_recent(context: AssetExecutionContext) -> dict:
    cp = CryptoPanicConnector.from_settings()
    articles = cp.fetch_recent()

    run_id = context.run_id or uuid.uuid4().hex
    now = datetime.now(tz=timezone.utc)
    key = f"cryptopanic/news/dt={now:%Y-%m-%d}/hh={now:%H}/{run_id}.jsonl.gz"
    count = put_jsonl_gz(
        bucket=settings.S3_BRONZE_BUCKET,
        key=key,
        records=(a.raw for a in articles),
    )
    context.add_output_metadata(
        {"records": count, "s3_key": MetadataValue.text(key)}
    )
    return {"key": key, "count": count, "run_id": run_id}


# ─── Silver ───────────────────────────────────────────────────


@asset(
    ins={"bronze": AssetIn("bronze_coingecko_spot")},
    description="Normalised spot prices in Postgres. Idempotent on instrument.",
    compute_kind="celery",
    group_name="silver",
)
def silver_price_spot(context: AssetExecutionContext, bronze: dict) -> int:
    # Delegate to Celery so it runs on the worker pool with retries.
    from pipelines.tasks.ingest import ingest_prices_for_active_instruments

    result = ingest_prices_for_active_instruments.apply_async(
        kwargs={"_run_id": bronze.get("run_id")},
    ).get(timeout=120)
    context.add_output_metadata({"rows_upserted": result})
    return result


@asset(
    partitions_def=DAILY,
    description="OHLCV candles per symbol per day, partitioned by date.",
    compute_kind="celery",
    group_name="silver",
)
def silver_price_candles(context: AssetExecutionContext) -> int:
    """Pull 1-minute candles for the day's partition for each tracked symbol."""
    from celery import group
    from pipelines.tasks.ingest import ingest_binance_klines

    # Production: read this list from a config or the catalog. Demo subset:
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

    pending = group(
        ingest_binance_klines.s(symbol=sym, resolution="1m", limit=1440)
        for sym in symbols
    ).apply_async()
    results = pending.get(timeout=300, disable_sync_subtasks=False)
    total = sum(results)
    context.add_output_metadata(
        {"rows_upserted": total, "symbols": len(symbols)},
    )
    return total


@asset(
    ins={"bronze": AssetIn("bronze_news_recent")},
    description="Normalised news articles with sentiment + symbol tagging.",
    compute_kind="celery",
    group_name="silver",
)
def silver_news_articles(context: AssetExecutionContext, bronze: dict) -> int:
    from pipelines.tasks.ingest import ingest_news_recent

    result = ingest_news_recent.apply_async(
        kwargs={"_run_id": bronze.get("run_id")},
    ).get(timeout=120)
    context.add_output_metadata({"rows_upserted": result})
    return result
