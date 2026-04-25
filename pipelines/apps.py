from django.apps import AppConfig


class PipelinesConfig(AppConfig):
    """`pipelines` is a Django app even though it has no models.

    Marking it as such gives Celery's `autodiscover_tasks()` a hook to find
    the task modules under `pipelines.tasks.*` without an early import that
    would touch the ORM before Django's app registry is ready.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "pipelines"
