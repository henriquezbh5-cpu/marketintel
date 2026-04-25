"""Middleware shared across the project."""
from __future__ import annotations

import uuid

from .request_context import set_request_id


class RequestIDMiddleware:
    """Attach an ID to every request and propagate it to logs.

    Honors an upstream `X-Request-ID` header (load balancer, gateway) when
    present so traces line up end-to-end.
    """

    HEADER = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(self.HEADER) or uuid.uuid4().hex
        request.request_id = request_id
        set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            set_request_id(None)
        response["X-Request-ID"] = request_id
        return response
