"""Minimal Python client for MarketIntel.

Demonstrates: auth via API key, listing instruments, paginating candles by
cursor, and querying news with filters.

Run:
    pip install httpx
    python examples/python_client.py --base-url http://localhost:8000 --api-key mi_xxx
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Iterator

import httpx


class MarketIntelClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            timeout=timeout,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
        )

    def list_instruments(self, **filters) -> list[dict]:
        return self._paginate("/api/v1/instruments/", params=filters)

    def get_candles(self, symbol: str, ts_from: datetime, ts_to: datetime,
                    resolution: str = "1m") -> Iterator[dict]:
        url = f"{self.base_url}/api/v1/candles/"
        params = {
            "symbol": symbol, "resolution": resolution,
            "ts_from": ts_from.isoformat(), "ts_to": ts_to.isoformat(),
            "page_size": 1000,
        }
        cursor = None
        while True:
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get(url, params=params).raise_for_status()
            page = resp.json()
            yield from page["results"]
            next_url = page.get("next")
            if not next_url:
                break
            cursor = httpx.URL(next_url).params.get("cursor")
            if not cursor:
                break

    def list_news(self, symbol: str | None = None, sentiment: str | None = None,
                  hours: int = 24) -> list[dict]:
        params: dict = {
            "published_from": (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat(),
        }
        if symbol:
            params["symbol"] = symbol
        if sentiment:
            params["sentiment"] = sentiment
        return self._paginate("/api/v1/news/", params=params)

    def _paginate(self, path: str, params: dict | None = None) -> list[dict]:
        url = f"{self.base_url}{path}"
        items: list[dict] = []
        while url:
            resp = self.client.get(url, params=params).raise_for_status()
            page = resp.json()
            if isinstance(page, list):
                return page
            items.extend(page.get("results", []))
            url = page.get("next")
            params = None
        return items


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--api-key", required=True)
    args = p.parse_args()

    client = MarketIntelClient(args.base_url, args.api_key)

    print("Top-3 instruments:")
    for inst in client.list_instruments()[:3]:
        print(f"  {inst['symbol']:6}  {inst['name']}")

    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(hours=2)
    print(f"\nLast 2h of BTC 1m candles (count):")
    candle_count = sum(1 for _ in client.get_candles("BTC", start, end, "1m"))
    print(f"  {candle_count} rows")

    print("\nNegative news in last 24h:")
    for art in client.list_news(sentiment="negative")[:5]:
        print(f"  [{art['sentiment']}] {art['title'][:70]}")


if __name__ == "__main__":
    main()
