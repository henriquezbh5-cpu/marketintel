from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.api.models import APIKey


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="bot", password="x")


@pytest.mark.integration
def test_valid_api_key_authenticates(user):
    raw, _ = APIKey.issue(user=user, name="ci")
    client = APIClient(HTTP_X_API_KEY=raw)
    response = client.get("/api/v1/sources/")
    assert response.status_code == 200


@pytest.mark.integration
def test_invalid_api_key_rejected(user):
    APIKey.issue(user=user, name="ci")
    client = APIClient(HTTP_X_API_KEY="mi_invalid")
    response = client.get("/api/v1/sources/")
    assert response.status_code in (401, 403)


@pytest.mark.integration
def test_inactive_key_rejected(user):
    raw, key = APIKey.issue(user=user, name="ci")
    key.is_active = False
    key.save()
    client = APIClient(HTTP_X_API_KEY=raw)
    response = client.get("/api/v1/sources/")
    assert response.status_code in (401, 403)


@pytest.mark.integration
def test_no_credentials_rejected():
    client = APIClient()
    response = client.get("/api/v1/sources/")
    assert response.status_code in (401, 403)
