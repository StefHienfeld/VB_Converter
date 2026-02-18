# hienfeld_api/middleware.py
"""
Security middleware for FastAPI application.
"""
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    # CSP for the API backend (does not serve frontend HTML).
    # frame-ancestors replaces X-Frame-Options in modern browsers.
    _CSP = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'none'"
    )

    # HSTS max-age: 1 year (31536000 seconds), include subdomains
    _HSTS = "max-age=31536000; includeSubDomains"

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = self._CSP
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Strict-Transport-Security: only set over HTTPS to avoid breaking HTTP dev.
        # Detects HTTPS via the X-Forwarded-Proto header (set by reverse proxies/load
        # balancers) or by the native TLS connection scheme reported by the ASGI scope.
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        is_https = forwarded_proto.lower() == "https" or request.url.scheme == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = self._HSTS

        # Request ID for tracing
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response.headers["X-Request-ID"] = request_id

        return response


# Global limiter instance — imported by app.py for decorator use
limiter = Limiter(key_func=get_remote_address)


def setup_security(app: FastAPI) -> None:
    """Configure security middleware for the application."""
    app.add_middleware(SecurityHeadersMiddleware)

    # SlowAPI rate limiting
    app.state.limiter = limiter
    app.add_middleware(SlowAPIASGIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_error_handler,
    )


async def _rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return 429 with a Dutch error message when rate limit is exceeded."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Te veel verzoeken. Probeer het over {exc.retry_after} seconden opnieuw."
        },
        headers={"Retry-After": str(exc.retry_after)},
    )
