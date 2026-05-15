"""HTTP middleware for request IDs and structured request logging."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.modules.shared.observability.context import reset_request_id, set_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id and log request lifecycle with stable fields."""

    def __init__(self, app, logger: logging.Logger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = set_request_id(request_id)
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started_at) * 1000.0
            self.logger.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            reset_request_id(token)

        duration_ms = (perf_counter() - started_at) * 1000.0
        response.headers["X-Request-ID"] = request_id
        self.logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
