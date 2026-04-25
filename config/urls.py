"""Root URL configuration.

Public exposure model:
  - `/api/v1/*`        → API key required (DRF auth)
  - `/api/docs/`       → public OpenAPI viewer (read-only)
  - `/api/schema/`     → public OpenAPI schema
  - `/health/*`        → public probes
  - `/admin/`          → only mounted when EXPOSE_ADMIN=true
  - `/metrics/`        → only mounted when EXPOSE_METRICS=true (default false in prod)

This way a Cloudflare/ngrok tunnel can be pointed at the service without
exposing the Django admin or Prometheus metrics to the internet.
"""
import os

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.health import live, ready


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() == "true"


EXPOSE_ADMIN = _flag("EXPOSE_ADMIN", default=True)
EXPOSE_METRICS = _flag("EXPOSE_METRICS", default=True)

urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("health/", live, name="health"),
    path("health/live/", live, name="health-live"),
    path("health/ready/", ready, name="health-ready"),
    path("api/v1/", include("apps.api.urls")),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

if EXPOSE_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))

if EXPOSE_METRICS:
    urlpatterns.append(path("metrics/", include("django_prometheus.urls")))
