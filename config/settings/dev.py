"""Development settings."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

INTERNAL_IPS = ["127.0.0.1"]

# Faster test runs / dev iteration
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Verbose SQL logging in dev (toggle as needed)
# LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"
