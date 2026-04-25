#!/usr/bin/env python
"""Mint a fresh API key for a user.

Usage:
    python scripts/issue_api_key.py <username> [--name NAME] [--scope read|write|admin]
"""
from __future__ import annotations

import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.api.models import APIKey  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("username")
    p.add_argument("--name", default="cli-issued")
    p.add_argument("--scope", default=APIKey.SCOPE_READ,
                   choices=[APIKey.SCOPE_READ, APIKey.SCOPE_WRITE, APIKey.SCOPE_ADMIN])
    args = p.parse_args()

    user = get_user_model().objects.get(username=args.username)
    raw, _ = APIKey.issue(user=user, name=args.name, scope=args.scope)

    print("API key issued. Save it now — it will NOT be shown again:")
    print()
    print(f"  {raw}")
    print()
    print(f"Use it as:  curl -H 'X-API-Key: {raw}' ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
