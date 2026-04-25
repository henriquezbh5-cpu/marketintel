"""API-specific persistent models.

Currently: APIKey for authentication. Kept here (rather than in `auth.py`)
so Django's `app.models` discovery picks them up without explicit imports.
"""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models


class APIKey(models.Model):
    """API key tied to a user, scoped, hashed at rest.

    Issuance:
        raw, key = APIKey.issue(user, name="ci-bot", scope="read")
        # `raw` shown to user once; we only persist the sha256 digest.
    """

    SCOPE_READ = "read"
    SCOPE_WRITE = "write"
    SCOPE_ADMIN = "admin"
    SCOPE_CHOICES = [
        (SCOPE_READ, "Read"),
        (SCOPE_WRITE, "Write"),
        (SCOPE_ADMIN, "Admin"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys",
    )
    name = models.CharField(max_length=64)
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    scope = models.CharField(max_length=32, default=SCOPE_READ, choices=SCOPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.scope})"

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user, name: str, scope: str = SCOPE_READ) -> tuple[str, "APIKey"]:
        """Generate a fresh key. Returns (raw_key, persisted_object).

        The raw key is shown to the user once; we only store its hash.
        """
        raw = f"mi_{secrets.token_urlsafe(32)}"
        api_key = cls.objects.create(
            user=user, name=name, scope=scope, key_hash=cls.hash_key(raw),
        )
        return raw, api_key
