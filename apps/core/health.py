"""Liveness and readiness probes.

Kubernetes-shaped:
  - /health/live   → process is up. No external deps checked.
  - /health/ready  → ready to serve traffic. Checks DB + Redis quickly.
  - /health/       → legacy, alias for live.

Probes must be cheap and bounded. We use short timeouts so a degraded
dependency doesn't block our pods from being killed by the kubelet.
"""
from __future__ import annotations

from django.db import OperationalError, connection
from django.http import JsonResponse


def live(_request):
    return JsonResponse({"status": "ok"})


def ready(_request):
    checks: dict[str, str] = {}

    # ─── Postgres ──────────────────────────────────────────────
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["postgres"] = "ok"
    except OperationalError as exc:
        checks["postgres"] = f"fail: {exc}"

    # ─── Redis (best-effort) ───────────────────────────────────
    try:
        from django.core.cache import cache
        cache.set("health_probe", "1", timeout=5)
        cache.get("health_probe")
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"fail: {exc}"

    overall_ok = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if overall_ok else "degraded", "checks": checks},
        status=200 if overall_ok else 503,
    )
