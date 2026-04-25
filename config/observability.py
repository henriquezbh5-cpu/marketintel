"""OpenTelemetry tracing setup.

Called from `wsgi.py` / `asgi.py` after Django is configured. Reads the
endpoint from `OTEL_EXPORTER_OTLP_ENDPOINT`; if missing, init is a no-op so
local dev runs without an OTel collector.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_tracing(service_name: str | None = None) -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel_imports_missing — skipping tracing init")
        return

    resource = Resource(attributes={
        "service.name": service_name or os.environ.get("OTEL_SERVICE_NAME", "marketintel"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    PsycopgInstrumentor().instrument(enable_commenter=True)
    logger.info("otel_tracing_initialised", extra={"endpoint": endpoint})
