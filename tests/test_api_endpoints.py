"""DRF endpoint smoke tests."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client(db, django_user_model):
    user = django_user_model.objects.create_user(username="tester", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.mark.integration
def test_instruments_list(client, btc_instrument, eth_instrument):
    response = client.get("/api/v1/instruments/")
    assert response.status_code == 200
    symbols = {row["symbol"] for row in response.json()["results"]}
    assert symbols == {"BTC", "ETH"}


@pytest.mark.integration
def test_candles_require_filter(client):
    response = client.get("/api/v1/candles/")
    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.integration
def test_sources_list(client, coingecko_source):
    response = client.get("/api/v1/sources/")
    assert response.status_code == 200
    assert any(row["code"] == "coingecko" for row in response.json())
