# ADR 0002 — Celery for distributed task processing

**Status**: Accepted · 2026-04-24

## Context

We need a task queue for ingestion fan-out (5K+ symbols/min), transformation
work, and DLQ handling. Candidates: Celery, RQ, arq, custom on top of Redis Streams.

## Decision

**Celery 5** with Redis as broker and result backend. Beat for periodic
schedules. Flower for local introspection.

## Rationale

- **Maturity**: ~15 years of production use, broad ecosystem, well-known failure
  modes.
- **Routing**: priorities, multiple queues, custom routes per task — we use
  `ingest`, `transform`, `default`, `dlq`.
- **Retries with backoff/jitter**: built in. We just declare on the task class.
- **Observability**: integrates with Prometheus, Sentry, OpenTelemetry.
- **Beat scheduler**: solid for our minute-level cadence; replaceable later
  if we want stronger guarantees (Celery Beat is single-instance).

## Trade-offs

- Celery is heavier than RQ. Worth it for the routing + retry semantics.
- Beat is single-instance — running two Beat schedulers double-fires. We
  mitigate via Kubernetes single-replica deployment + leader election if
  scaling becomes an issue.
- Result backend on Redis adds memory pressure when we keep results long.
  We TTL aggressively (24h) and don't depend on results except where needed.

## Alternatives considered

- **RQ**: simpler but lacks Beat, lacks routing, weaker retry semantics.
- **arq**: async-first; would force every task to be coroutine-based. Ruled
  out because Django ORM stays sync.
- **Redis Streams + custom workers**: more control but reinvents queueing.
  Not justified given the existing options.
- **Dagster alone**: covers orchestration but is not designed for high-frequency
  fan-out at our scale. Used in tandem (see ADR 0003).
