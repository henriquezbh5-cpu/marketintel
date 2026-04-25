"""Token bucket — covers the rate limiting at the connector base."""
from __future__ import annotations

import time

import pytest

from pipelines.connectors.base import TokenBucket


@pytest.mark.unit
def test_initial_capacity_is_full():
    b = TokenBucket(rate_per_min=60, capacity=10)
    # First 10 takes succeed without waiting
    for _ in range(10):
        assert b.take() == 0.0


@pytest.mark.unit
def test_take_returns_wait_when_empty():
    b = TokenBucket(rate_per_min=60, capacity=1)
    assert b.take() == 0.0
    wait = b.take()
    assert wait > 0


@pytest.mark.unit
def test_refills_over_time():
    b = TokenBucket(rate_per_min=600, capacity=1)  # 10/sec
    b.take()
    time.sleep(0.2)
    # After 200ms we should have refilled enough for at least one token.
    assert b.take() == 0.0
