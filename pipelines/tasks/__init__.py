"""Re-export task modules so Celery's autodiscover finds them.

Imports happen at autodiscover time, which is *after* Django's app registry
is ready, so it's safe to touch ORM models in the task modules below.
"""
from .ingest import *  # noqa: F401, F403
from .maintenance import *  # noqa: F401, F403
from .transform import *  # noqa: F401, F403
