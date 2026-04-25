import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()

# Initialise OTel after Django is wired so instrumentations can attach.
from config.observability import init_tracing  # noqa: E402

init_tracing(service_name="marketintel-web")
