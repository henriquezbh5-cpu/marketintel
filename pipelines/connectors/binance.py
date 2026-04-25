"""Binance public market-data adapter.

Spot endpoints used here are fully public; no key required for read-only data.
Docs: https://binance-docs.github.io/apidocs/spot/en/
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.conf import settings

from .base import BaseConnector


@dataclass(frozen=True)
class BinanceCandle:
    symbol: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    raw: tuple


_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}


class BinanceConnector(BaseConnector):
    source_code = "binance"

    @classmethod
    def from_settings(cls) -> "BinanceConnector":
        return cls(
            base_url=settings.BINANCE_BASE_URL,
            rate_limit_per_min=settings.BINANCE_RATE_LIMIT_PER_MIN,
        )

    # ── Endpoints ──────────────────────────────────────────────
    def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> list[BinanceCandle]:
        """OHLCV candles. Symbol example: BTCUSDT."""
        if interval not in _INTERVAL_MAP:
            raise ValueError(f"unsupported interval {interval!r}")

        data = self._get(
            "/api/v3/klines",
            params={"symbol": symbol, "interval": _INTERVAL_MAP[interval], "limit": limit},
        )
        return [
            BinanceCandle(
                symbol=symbol,
                open_time=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                open=Decimal(row[1]),
                high=Decimal(row[2]),
                low=Decimal(row[3]),
                close=Decimal(row[4]),
                volume=Decimal(row[5]),
                raw=tuple(row),
            )
            for row in data
        ]
