# hienfeld_api/middleware.py
"""
Security middleware for FastAPI application.
"""
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Request ID for tracing
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response.headers["X-Request-ID"] = request_id

        return response


def setup_security(app: FastAPI) -> None:
    """Configure security middleware for the application."""
    app.add_middleware(SecurityHeadersMiddleware)
