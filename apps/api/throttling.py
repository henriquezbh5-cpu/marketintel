"""Custom throttle keyed off the API key when present (else IP).

DRF's default `ScopedRateThrottle` keys on user PK or IP. With API keys we
prefer the key id so a single user with multiple keys gets independent
buckets per key — useful when a key is shared across services.
"""
from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle


class APIKeyScopedThrottle(ScopedRateThrottle):
    def get_cache_key(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is not None and hasattr(api_key, "pk"):
            ident = f"key:{api_key.pk}"
        elif request.user and request.user.is_authenticated:
            ident = f"user:{request.user.pk}"
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": getattr(view, "throttle_scope", "default"),
            "ident": ident,
        }
