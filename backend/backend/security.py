"""HTTP security controls shared by the FastAPI app."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.config import settings
from backend.errors import AppError


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _origin_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative browser security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.hsts_enabled and request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class OriginProtectionMiddleware(BaseHTTPMiddleware):
    """Reject browser cross-site state-changing requests for cookie-auth endpoints."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if settings.enforce_origin_checks and request.method.upper() not in SAFE_METHODS:
            origin = request.headers.get("origin")
            referer_origin = _origin_from_url(request.headers.get("referer"))
            supplied_origin = origin or referer_origin
            if supplied_origin:
                allowed = set(settings.cors_allowed_origins)
                allowed.add(_request_origin(request))
                if supplied_origin.rstrip("/") not in {item.rstrip("/") for item in allowed}:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "invalid_request_origin",
                            "detail": "Request origin is not allowed",
                        },
                    )
        return await call_next(request)


@dataclass(slots=True)
class InMemoryRateLimiter:
    """Small process-local sliding-window limiter for sensitive endpoints."""

    _buckets: defaultdict[str, deque[float]]

    def __init__(self) -> None:
        self._buckets = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = monotonic()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


rate_limiter = InMemoryRateLimiter()


def client_key(request: Request, namespace: str, discriminator: str | None = None) -> str:
    host = request.client.host if request.client else "unknown"
    suffix = f":{discriminator.strip().lower()}" if discriminator else ""
    return f"{namespace}:{host}{suffix}"


def enforce_rate_limit(request: Request, namespace: str, *, discriminator: str | None, limit: int, window_seconds: int) -> None:
    if rate_limiter.hit(client_key(request, namespace, discriminator), limit=limit, window_seconds=window_seconds):
        return
    raise AppError(429, "rate_limit_exceeded", "Too many requests; please try again later")
