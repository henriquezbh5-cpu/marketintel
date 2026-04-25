"""Centralised Prometheus metrics for the platform.

Imported by tasks/connectors to record events. Names are stable — referenced
by Grafana dashboards and Prometheus alerting rules.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ─── Connector layer ───────────────────────────────────────────
connector_request_count = Counter(
    "connector_request_count",
    "Total HTTP calls to upstream sources",
    ["source", "status"],
)
connector_request_duration_seconds = Histogram(
    "connector_request_duration_seconds",
    "Latency of upstream HTTP calls",
    ["source"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
connector_breaker_open_total = Counter(
    "connector_breaker_open_total",
    "Times the connector circuit breaker tripped",
    ["source"],
)

# ─── Pipeline layer ────────────────────────────────────────────
pipeline_rows_written = Counter(
    "pipeline_rows_written",
    "Rows persisted by ingestion / transformation",
    ["layer", "table"],
)
last_ingest_ts = Gauge(
    "marketintel_last_ingest_ts",
    "Unix ts of last successful ingest per source",
    ["source"],
)
dlq_inserts_total = Counter(
    "marketintel_dlq_inserts_total",
    "Tasks dead-lettered",
    ["task_name"],
)
dlq_size = Gauge(
    "marketintel_dlq_size",
    "Current size of the DLQ table",
)
