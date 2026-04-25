"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.health import live, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", live, name="health"),
    path("health/live/", live, name="health-live"),
    path("health/ready/", ready, name="health-ready"),
    path("metrics/", include("django_prometheus.urls")),
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
