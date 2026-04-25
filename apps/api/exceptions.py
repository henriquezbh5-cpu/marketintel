"""Project-wide DRF exception handler.

Wraps DRF's default to:
  - log all 5xx with the request_id
  - include the request_id in every error response (so the client can quote
    it back when filing tickets)
"""
from __future__ import annotations

import logging

from rest_framework.views import exception_handler as drf_default_handler

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    response = drf_default_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    if response is None:
        # Truly unhandled — log it loudly. DRF would have returned None and
        # let Django's 500 page take over; we keep the same behavior but
        # leave a structured trace.
        logger.exception(
            "unhandled_view_error",
            extra={"request_id": request_id, "path": getattr(request, "path", None)},
        )
        return None

    if response.status_code >= 500:
        logger.error(
            "view_error",
            extra={
                "request_id": request_id,
                "status": response.status_code,
                "exception": str(exc),
            },
        )

    if isinstance(response.data, dict):
        response.data.setdefault("request_id", request_id)
    response["X-Request-ID"] = request_id or ""
    return response
