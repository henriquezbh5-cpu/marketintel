"""CoinGecko connector — uses respx to stub HTTP without recording cassettes.

vcrpy is also acceptable; respx is lighter when we just want to stub responses.
"""
from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from pipelines.connectors.coingecko import CoinGeckoConnector


@pytest.fixture
def cg() -> CoinGeckoConnector:
    return CoinGeckoConnector(
        base_url="https://api.coingecko.com/api/v3",
        rate_limit_per_min=60,
    )


@pytest.mark.unit
@respx.mock
def test_list_coins_parses_response(cg):
    respx.get("https://api.coingecko.com/api/v3/coins/list").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
                {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
            ],
        ),
    )

    coins = cg.list_coins()
    assert len(coins) == 2
    assert coins[0].coin_id == "bitcoin"
    assert coins[0].symbol == "BTC"  # uppercased


@pytest.mark.unit
@respx.mock
def test_fetch_spot_returns_typed_records(cg):
    respx.get("https://api.coingecko.com/api/v3/coins/markets").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "current_price": 60000.5,
                    "price_change_percentage_24h": 1.23,
                    "total_volume": 12345678.9,
                },
            ],
        ),
    )
    spots = cg.fetch_spot(["bitcoin"])
    assert len(spots) == 1
    assert spots[0].price_usd == Decimal("60000.5")
    assert spots[0].change_24h_pct == Decimal("1.23")


@pytest.mark.unit
@respx.mock
def test_429_raises_rate_limited(cg):
    from pipelines.connectors.base import RateLimited

    respx.get("https://api.coingecko.com/api/v3/coins/list").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "10"}),
    )

    with pytest.raises(RateLimited) as exc_info:
        cg.list_coins()

    assert exc_info.value.retry_after == 10.0


@pytest.mark.unit
@respx.mock
def test_5xx_trips_breaker_after_threshold(cg):
    from pipelines.connectors.base import CircuitOpen, ConnectorError

    respx.get("https://api.coingecko.com/api/v3/coins/list").mock(
        return_value=httpx.Response(503),
    )

    for _ in range(cg.breaker.failure_threshold):
        with pytest.raises(ConnectorError):
            cg.list_coins()

    # Next call should fail fast on the open breaker.
    with pytest.raises(CircuitOpen):
        cg.list_coins()
