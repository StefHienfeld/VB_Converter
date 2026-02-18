"""
Middleware package for VB_Converter API.
"""

from .security import setup_security, SecurityHeadersMiddleware, RequestLoggingMiddleware

# Import limiter from slowapi for rate limiting decorators
from slowapi import Limiter
from slowapi.util import get_remote_address

# Global limiter instance - imported by app.py for decorator use
limiter = Limiter(key_func=get_remote_address)

__all__ = ["setup_security", "SecurityHeadersMiddleware", "RequestLoggingMiddleware", "limiter"]
