"""Yahoo Finance adapter — public chart endpoint, no API key.

Endpoint:
  GET https://query1.finance.yahoo.com/v8/finance/chart/<symbol>
      ?interval=1m|5m|15m|1h|1d&range=1d|5d|1mo|3mo|6mo|1y|max

Yahoo's terms restrict commercial redistribution, but free for read access.
For production-grade ingestion at scale, swap for a paid provider (Polygon,
Finnhub, Refinitiv) — the connector contract stays identical.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.conf import settings

from .base import BaseConnector


@dataclass(frozen=True)
class YFCandle:
    symbol: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class YFQuote:
    """Latest snapshot derived from the chart meta block."""
    symbol: str
    name: str
    price: Decimal
    previous_close: Decimal | None
    change_pct: Decimal | None
    volume: Decimal
    market_cap: Decimal | None
    currency: str
    exchange: str
    ts: datetime


# ── Resolution mapping ────────────────────────────────────────
_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "60m", "4h": "60m",   # 4h not native; we resample upstream when needed
    "1d": "1d",
}

# Yahoo only allows certain interval/range combinations.
_DEFAULT_RANGE = {
    "1m":  "1d",   # 1m only available for the last day
    "5m":  "5d",
    "15m": "5d",
    "1h":  "1mo",
    "4h":  "3mo",
    "1d":  "6mo",
}


class YahooFinanceConnector(BaseConnector):
    source_code = "yahoo_finance"

    @classmethod
    def from_settings(cls) -> "YahooFinanceConnector":
        return cls(
            base_url=getattr(settings, "YAHOO_BASE_URL", "https://query1.finance.yahoo.com"),
            rate_limit_per_min=getattr(settings, "YAHOO_RATE_LIMIT_PER_MIN", 60),
        )

    def auth_headers(self) -> Mapping[str, str]:
        # Yahoo serves anonymous JSON if requests look like a browser.
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        }

    # ── Endpoints ──────────────────────────────────────────────
    def fetch_chart(
        self,
        symbol: str,
        resolution: str = "1m",
        range_: str | None = None,
    ) -> tuple[YFQuote | None, list[YFCandle]]:
        if resolution not in _INTERVAL:
            raise ValueError(f"unsupported resolution {resolution!r}")
        interval = _INTERVAL[resolution]
        rng = range_ or _DEFAULT_RANGE[resolution]

        payload = self._get(
            f"/v8/finance/chart/{symbol}",
            params={"interval": interval, "range": rng, "includePrePost": "false"},
        )
        return self._parse_chart(symbol, resolution, payload)

    def fetch_quote(self, symbol: str) -> YFQuote | None:
        """Latest snapshot. We piggyback on the 1m chart endpoint to keep one
        code path and avoid the (auth-gated) `/v7/quote` endpoint."""
        quote, _ = self.fetch_chart(symbol, resolution="1m")
        return quote

    # ── Internal ───────────────────────────────────────────────
    def _parse_chart(
        self, symbol: str, resolution: str, payload: dict,
    ) -> tuple[YFQuote | None, list[YFCandle]]:
        chart = payload.get("chart") or {}
        if chart.get("error"):
            err = chart["error"]
            from .base import ConnectorError
            raise ConnectorError(f"{err.get('code')}: {err.get('description')}")
        results = chart.get("result") or []
        if not results:
            return (None, [])
        result = results[0]

        # Quote (meta)
        meta = result.get("meta") or {}
        ts_now = datetime.fromtimestamp(meta.get("regularMarketTime") or 0, tz=timezone.utc) \
            if meta.get("regularMarketTime") else datetime.now(tz=timezone.utc)
        price = _dec(meta.get("regularMarketPrice"))
        prev = _dec(meta.get("chartPreviousClose")) or _dec(meta.get("previousClose"))
        change_pct = None
        if price is not None and prev is not None and prev != Decimal("0"):
            change_pct = ((price - prev) / prev) * Decimal("100")

        quote = YFQuote(
            symbol=symbol.upper(),
            name=meta.get("longName") or meta.get("shortName") or symbol.upper(),
            price=price or Decimal("0"),
            previous_close=prev,
            change_pct=change_pct,
            volume=_dec(meta.get("regularMarketVolume")) or Decimal("0"),
            market_cap=_dec(meta.get("marketCap")),
            currency=meta.get("currency") or "USD",
            exchange=meta.get("exchangeName") or meta.get("fullExchangeName") or "",
            ts=ts_now,
        )

        # Candles
        timestamps = result.get("timestamp") or []
        indicators = (result.get("indicators") or {}).get("quote") or []
        if not timestamps or not indicators:
            return (quote, [])
        q = indicators[0]
        opens, highs, lows, closes, vols = (
            q.get("open") or [], q.get("high") or [],
            q.get("low") or [], q.get("close") or [], q.get("volume") or [],
        )
        candles: list[YFCandle] = []
        for i, t in enumerate(timestamps):
            o, h, l, c, v = (
                opens[i] if i < len(opens) else None,
                highs[i] if i < len(highs) else None,
                lows[i] if i < len(lows) else None,
                closes[i] if i < len(closes) else None,
                vols[i] if i < len(vols) else None,
            )
            # Yahoo emits null for missing minutes (gaps, holidays). Skip them.
            if None in (o, h, l, c):
                continue
            candles.append(YFCandle(
                symbol=symbol.upper(),
                open_time=datetime.fromtimestamp(t, tz=timezone.utc),
                open=_dec(o) or Decimal("0"),
                high=_dec(h) or Decimal("0"),
                low=_dec(l) or Decimal("0"),
                close=_dec(c) or Decimal("0"),
                volume=_dec(v) or Decimal("0"),
            ))
        return (quote, candles)


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
