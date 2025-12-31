"""
Security middleware for VB_Converter API.

Provides:
- Security headers (X-Frame-Options, CSP, etc.)
- Request logging for audit trail
- Rate limiting (optional)
"""

import time
import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from hienfeld.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS only in production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests for audit trail."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(int(time.time() * 1000)))
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log request (skip health checks to reduce noise)
        if not request.url.path.endswith("/health"):
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                }
            )

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        return response


def setup_security(app: FastAPI) -> None:
    """
    Configure all security middleware for the application.

    Should be called after CORS middleware is added.

    Args:
        app: FastAPI application instance
    """
    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request logging (audit trail)
    app.add_middleware(RequestLoggingMiddleware)

    # Rate limiting using slowapi (if enabled)
    if settings.rate_limit_enabled:
        try:
            from slowapi import Limiter, _rate_limit_exceeded_handler
            from slowapi.util import get_remote_address
            from slowapi.errors import RateLimitExceeded

            limiter = Limiter(key_func=get_remote_address)
            app.state.limiter = limiter
            app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

            logger.info(
                f"Rate limiting enabled: {settings.rate_limit_requests} requests per {settings.rate_limit_window}s"
            )
        except ImportError:
            logger.warning("slowapi not installed - rate limiting disabled")
