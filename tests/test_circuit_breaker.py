from __future__ import annotations

import time

import pytest

from pipelines.connectors.base import CircuitBreaker


@pytest.mark.unit
def test_breaker_opens_after_threshold_failures():
    b = CircuitBreaker(failure_threshold=3, cooldown_s=10)
    assert b.allow() is True

    b.record_failure()
    b.record_failure()
    assert b.allow() is True  # still under threshold

    b.record_failure()
    assert b.allow() is False  # opened


@pytest.mark.unit
def test_breaker_half_opens_after_cooldown():
    b = CircuitBreaker(failure_threshold=2, cooldown_s=0.05)
    b.record_failure()
    b.record_failure()
    assert b.allow() is False
    time.sleep(0.06)
    assert b.allow() is True  # half-open


@pytest.mark.unit
def test_success_resets_failure_count():
    b = CircuitBreaker(failure_threshold=2, cooldown_s=10)
    b.record_failure()
    b.record_success()
    b.record_failure()
    assert b.allow() is True  # counter was reset
