"""API key authentication.

Header: `X-API-Key: <raw_key>` → resolved to a Django user.
Persistence: the raw key is hashed (sha256) before lookup; only the digest
lives in the DB. See `apps.api.models.APIKey.issue` to mint new keys.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import APIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    keyword = "X-API-Key"

    def authenticate(self, request):
        raw = request.META.get("HTTP_X_API_KEY")
        if not raw:
            return None

        digest = APIKey.hash_key(raw)
        try:
            api_key = APIKey.objects.select_related("user").get(
                key_hash=digest, is_active=True,
            )
        except APIKey.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid API key") from exc

        # Best-effort timestamp; we don't fail auth if this fails (e.g. read replica).
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        return (api_key.user, api_key)
