"""Production middleware: security headers, request context/access logs,
Prometheus metrics, and Redis-backed rate limiting (fail-open)."""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.metrics import RATE_LIMITED, REQUEST_COUNT, REQUEST_LATENCY

log = structlog.get_logger("access")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
            )
            if settings.is_production:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id, emit an access log, and record metrics."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        duration = time.perf_counter() - start
        path = _route_template(request)
        REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 1),
            request_id=request_id,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-client rate limit via Redis. Fail-open if Redis is down."""

    def __init__(self, app):
        super().__init__(app)
        self._redis = None

    async def _client(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _limit_for(self, path: str) -> int:
        if path.startswith(f"{settings.api_v1_prefix}/auth"):
            return settings.auth_rate_limit_per_minute
        return settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled or not request.url.path.startswith(
            settings.api_v1_prefix
        ):
            return await call_next(request)

        ip = (request.client.host if request.client else "unknown")
        window = int(time.time() // 60)
        limit = self._limit_for(request.url.path)
        key = f"rl:{ip}:{window}:{'auth' if 'auth' in request.url.path else 'api'}"

        try:
            client = await self._client()
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, 60)
            if count > limit:
                RATE_LIMITED.inc()
                return JSONResponse(
                    status_code=429,
                    media_type="application/problem+json",
                    headers={"Retry-After": "60"},
                    content={
                        "type": "about:blank",
                        "title": "Too Many Requests",
                        "status": 429,
                        "detail": f"Rate limit of {limit}/min exceeded",
                        "instance": request.url.path,
                    },
                )
        except Exception as exc:  # noqa: BLE001 — fail open if Redis unavailable
            log.warning("rate limit check skipped", error=str(exc))

        return await call_next(request)
