# ADR 0007 — Structured logging with JSON + request IDs

**Status**: Accepted · 2026-04-24

## Context

Across Django views, Celery workers, Dagster ops and connector calls, we
want log lines that:
1. Carry a stable request/run identifier across hops.
2. Are machine-parseable end-to-end (Loki / Datadog / CloudWatch).
3. Include business keys (symbol, source, partition) so we can grep
   incidents by the thing the customer cares about.

## Decision

- All logs emit **JSON Lines** to stdout via a custom `JSONFormatter`.
- A `RequestIDMiddleware` injects/propagates `X-Request-ID`.
- A `ContextVar` carries the request id across async / Celery hops; the
  formatter reads it for each record.
- Celery tasks use `_run_id` as the equivalent identifier; it's added to
  every structured log inside a task.

## Rationale

- JSON over plain text means downstream tools never have to regex log lines.
- ContextVar > ThreadLocal because it propagates through `asyncio` correctly.
- The same request id flowing API → Celery → Postgres lets us correlate a
  user complaint to the exact upstream call that produced bad data.

## Trade-offs

- JSON logs are noisier in a tail. We accept it; pretty-printing is for
  ad-hoc shell debugging.
- Carrying request id through Celery means we propagate it via task headers
  (or kwargs); we chose kwargs for explicitness even though it pollutes the
  signature. Consistency wins.

## Alternatives considered

- **structlog + processors only**: nice DX but adds a dependency we don't
  fully use. Our `JSONFormatter` is ~30 lines; it suffices.
- **OpenTelemetry traces only**: complementary, not a replacement. We add
  OTel for traces in addition to structured logs.
