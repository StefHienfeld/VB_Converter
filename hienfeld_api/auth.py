"""
JWT authentication utilities for Hienfeld VB Converter API.

Provides:
- Password hashing (bcrypt via passlib)
- JWT token creation and verification (python-jose)
- FastAPI dependency for protecting endpoints

Configuration (via environment variables):
    SECRET_KEY           - JWT signing key (generate: openssl rand -hex 32)
    JWT_ALGORITHM        - Algorithm (default: HS256)
    JWT_EXPIRE_MINUTES   - Access token lifetime (default: 480 = 8 hours)
    AUTH_ENABLED         - Enable/disable auth entirely (default: True in production)
    ADMIN_USERNAME       - Default admin username (default: admin)
    ADMIN_PASSWORD_HASH  - bcrypt hash of admin password

To generate a password hash:
    python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('yourpassword'))"
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Password hashing
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Constants (loaded from settings on first use)
# ---------------------------------------------------------------------------

# Default algorithm
JWT_ALGORITHM = "HS256"

# Default token lifetime (8 hours — a working day)
JWT_EXPIRE_MINUTES = 480


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


def create_access_token(
    subject: str,
    secret_key: str,
    expires_minutes: int = JWT_EXPIRE_MINUTES,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: The user identifier (username or user ID)
        secret_key: HMAC signing key from settings
        expires_minutes: Token validity window

    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    subject: str,
    secret_key: str,
    expires_days: int = 7,
) -> str:
    """
    Create a signed JWT refresh token (longer lived).

    Args:
        subject: The user identifier
        secret_key: HMAC signing key from settings
        expires_days: Refresh token validity window

    Returns:
        Encoded JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str, secret_key: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: Raw JWT string
        secret_key: HMAC signing key

    Returns:
        Token payload dict

    Raises:
        JWTError: If token is invalid, expired, or tampered
    """
    return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_current_user_dependency(settings):
    """
    Factory that returns a FastAPI dependency for JWT validation.

    Args:
        settings: App settings instance (has secret_key, auth_enabled)

    Returns:
        Async dependency callable

    Usage:
        router = APIRouter(dependencies=[Depends(get_current_user_dependency(settings))])
    """

    async def _get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    ) -> str:
        """
        Extract and validate JWT from Authorization: Bearer <token> header.

        Returns:
            Username (subject claim) if valid

        Raises:
            401 Unauthorized if token is missing or invalid
        """
        # Auth disabled — log a prominent warning so this is never silent in production.
        if not getattr(settings, "auth_enabled", True):
            logger.warning(
                "SECURITY WARNING: Authentication is DISABLED (AUTH_ENABLED=false). "
                "All endpoints are publicly accessible without a valid token. "
                "Set AUTH_ENABLED=true in production!"
            )
            return "dev-user"

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticatie vereist. Stuur een geldig Bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = decode_token(credentials.credentials, settings.secret_key)
            subject: Optional[str] = payload.get("sub")
            token_type: str = payload.get("type", "access")

            if subject is None or token_type != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Ongeldig token.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return subject

        except JWTError as exc:
            logger.warning("JWT validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verlopen of ongeldig. Log opnieuw in.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    return _get_current_user
