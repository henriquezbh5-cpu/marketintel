"""Settings used by pytest. Optimised for fast CI runs."""
from .base import *  # noqa: F401, F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Run Celery tasks eagerly in tests, no broker required
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use locmem cache to avoid Redis dependency in unit tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Faster migrations in tests (no real schema work for unit tests)
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": "test_marketintel",
}

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
