"""Shared pytest fixtures."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.instruments.models import Instrument, Source


@pytest.fixture
def coingecko_source(db):
    return Source.objects.create(
        code="coingecko",
        name="CoinGecko",
        base_url="https://api.coingecko.com/api/v3",
        is_active=True,
    )


@pytest.fixture
def binance_source(db):
    return Source.objects.create(
        code="binance",
        name="Binance",
        base_url="https://api.binance.com",
        is_active=True,
    )


@pytest.fixture
def btc_instrument(db, coingecko_source):
    return Instrument.objects.create(
        source=coingecko_source,
        external_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        asset_class="crypto",
        quote_currency="USD",
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        is_current=True,
    )


@pytest.fixture
def eth_instrument(db, coingecko_source):
    return Instrument.objects.create(
        source=coingecko_source,
        external_id="ethereum",
        symbol="ETH",
        name="Ethereum",
        asset_class="crypto",
        quote_currency="USD",
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        is_current=True,
    )


@pytest.fixture
def utc_now():
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def decimal():
    return Decimal
