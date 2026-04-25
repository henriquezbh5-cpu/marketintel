"""Base for third-party API connectors.

Every adapter inherits from `BaseConnector`. The base layer provides:

  - HTTP client (httpx) configured with timeouts and connection pooling
  - Retries with exponential backoff + jitter (handled by the calling task,
    not here — connectors raise typed exceptions and let the task layer decide)
  - Token-bucket rate limiting per connector instance
  - Circuit breaker (open / half-open / closed)
  - Structured logging on every request

Adapters implement the *thin* surface: which endpoints exist, how to map
params to URLs, how to translate raw responses to pydantic records. Cross-
cutting concerns live here.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ─── Errors ────────────────────────────────────────────────────
class ConnectorError(Exception):
    """Base for all connector errors."""


class RateLimited(ConnectorError):
    """Upstream signaled rate limiting (HTTP 429 or our local bucket)."""

    def __init__(self, retry_after: float | None = None):
        super().__init__("rate limited")
        self.retry_after = retry_after


class CircuitOpen(ConnectorError):
    """Circuit breaker is open — fail fast without hitting upstream."""


# ─── Token bucket ──────────────────────────────────────────────
class TokenBucket:
    """Simple thread-safe token bucket. Refills continuously."""

    def __init__(self, rate_per_min: int, capacity: int | None = None):
        self.rate_per_sec = rate_per_min / 60.0
        self.capacity = capacity or rate_per_min
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def take(self, n: int = 1) -> float:
        """Take n tokens. Returns 0 if available, else seconds to wait."""
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate_per_sec)
            self._last = now
            if self._tokens >= n:
                self._tokens -= n
                return 0.0
            deficit = n - self._tokens
            return deficit / self.rate_per_sec


# ─── Circuit breaker ───────────────────────────────────────────
@dataclass
class CircuitBreaker:
    """Half-open after `cooldown_s`. Opens after `failure_threshold` consecutive failures."""

    failure_threshold: int = 5
    cooldown_s: float = 30.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if time.monotonic() - self._opened_at >= self.cooldown_s:
                # Half-open: allow one probe
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()


# ─── Base connector ────────────────────────────────────────────
class BaseConnector:
    """Synchronous HTTP connector.

    Subclasses set:
      - `source_code`: must match a `Source.code` row
      - `default_timeout_s`: per-request timeout
    And implement endpoint-specific methods that call `self._get(...)`.
    """

    source_code: str = ""
    default_timeout_s: float = 30.0

    def __init__(
        self,
        base_url: str,
        rate_limit_per_min: int,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.bucket = TokenBucket(rate_limit_per_min)
        self.breaker = CircuitBreaker()
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(self.default_timeout_s),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"User-Agent": "MarketIntel/0.1 (+https://example.com)"},
        )

    # ── Hooks for subclasses ───────────────────────────────────
    def auth_headers(self) -> Mapping[str, str]:
        return {}

    # ── Core request ───────────────────────────────────────────
    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict:
        from apps.core.metrics import (
            connector_breaker_open_total,
            connector_request_count,
            connector_request_duration_seconds,
        )

        if not self.breaker.allow():
            connector_breaker_open_total.labels(source=self.source_code).inc()
            raise CircuitOpen(f"{self.source_code} breaker open")

        wait_s = self.bucket.take()
        if wait_s > 0:
            # Surface rate limit as a typed error rather than silently sleeping;
            # the task layer can decide to back off / re-queue.
            raise RateLimited(retry_after=wait_s)

        url = f"{self.base_url}/{path.lstrip('/')}"
        with connector_request_duration_seconds.labels(source=self.source_code).time():
            try:
                response = self.client.get(url, params=params, headers=self.auth_headers())
            except httpx.HTTPError as exc:
                self.breaker.record_failure()
                connector_request_count.labels(source=self.source_code, status="error").inc()
                logger.warning(
                    "connector_http_error",
                    extra={"source": self.source_code, "path": path, "error": str(exc)},
                )
                raise ConnectorError(str(exc)) from exc

        connector_request_count.labels(
            source=self.source_code, status=str(response.status_code),
        ).inc()

        if response.status_code == 429:
            self.breaker.record_failure()
            retry_after = float(response.headers.get("Retry-After", "5"))
            raise RateLimited(retry_after=retry_after)

        if response.status_code >= 500:
            self.breaker.record_failure()
            raise ConnectorError(f"upstream {response.status_code}")

        if response.status_code >= 400:
            # 4xx is not a transient failure, don't trip the breaker.
            raise ConnectorError(
                f"{response.status_code}: {response.text[:200]}",
            )

        self.breaker.record_success()
        return response.json()
