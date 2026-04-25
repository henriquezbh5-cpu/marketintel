"""Ad-hoc ingestion entrypoint.

Usage:
    python manage.py ingest --source coingecko
    python manage.py ingest --source binance --symbols BTCUSDT,ETHUSDT --resolution 1m
    python manage.py ingest --source cryptopanic
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Trigger an ingestion synchronously (bypasses Celery / Dagster)."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, choices=["coingecko", "binance", "cryptopanic"])
        parser.add_argument("--symbols", default="", help="Comma-separated, source-specific")
        parser.add_argument("--resolution", default="1m")
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, source: str, symbols: str, resolution: str, limit: int, **_):
        symbols_list = [s.strip() for s in symbols.split(",") if s.strip()]

        if source == "coingecko":
            from pipelines.tasks.ingest import ingest_prices_for_active_instruments
            count = ingest_prices_for_active_instruments.apply().get()
            self.stdout.write(self.style.SUCCESS(f"upserted {count} spots"))

        elif source == "binance":
            if not symbols_list:
                raise CommandError("--symbols required for binance (e.g. BTCUSDT,ETHUSDT)")
            from pipelines.tasks.ingest import ingest_binance_klines
            total = 0
            for symbol in symbols_list:
                total += ingest_binance_klines.apply(
                    args=(symbol,),
                    kwargs={"resolution": resolution, "limit": limit},
                ).get()
            self.stdout.write(self.style.SUCCESS(f"upserted {total} candles"))

        elif source == "cryptopanic":
            from pipelines.tasks.ingest import ingest_news_recent
            count = ingest_news_recent.apply(
                args=(tuple(symbols_list),),
            ).get()
            self.stdout.write(self.style.SUCCESS(f"upserted {count} articles"))
