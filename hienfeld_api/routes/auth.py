"""
Authentication endpoints for Hienfeld VB Converter API.

Provides:
- POST /auth/login  - Exchange username/password for JWT tokens
- POST /auth/refresh - Exchange refresh token for new access token
- GET  /auth/me     - Get current authenticated user info

Single-user authentication: credentials are configured via environment
variables (ADMIN_USERNAME, ADMIN_PASSWORD_HASH). No user management UI
required for the initial implementation.

To add users later: extend with a SQLAlchemy users table.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from hienfeld_api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login credentials."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class MeResponse(BaseModel):
    """Current user info."""
    username: str
    authenticated: bool


# ---------------------------------------------------------------------------
# Helper: get admin credentials from settings
# ---------------------------------------------------------------------------


def _get_settings():
    from hienfeld.settings import get_settings
    return get_settings()


def _authenticate_user(username: str, password: str, settings) -> bool:
    """
    Validate username + password against configured admin credentials.

    Uses bcrypt comparison (constant-time) to prevent timing attacks.
    """
    expected_username = getattr(settings, "admin_username", "admin")
    password_hash = getattr(settings, "admin_password_hash", None)

    if username != expected_username:
        return False

    if password_hash is None:
        # No hash configured — allow login with default password in dev only
        if getattr(settings, "is_production", False):
            logger.error("ADMIN_PASSWORD_HASH not configured in production!")
            return False
        logger.warning("ADMIN_PASSWORD_HASH not set — using default 'admin' password (dev only!)")
        return password == "admin"

    return verify_password(password, password_hash)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    settings=Depends(_get_settings),
) -> TokenResponse:
    """
    Authenticate with username and password.

    Returns access token (8h) and refresh token (7d).
    Use the access token as: Authorization: Bearer <access_token>
    """
    if not _authenticate_user(request.username, request.password, settings):
        logger.warning("Failed login attempt for username: %s", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gebruikersnaam of wachtwoord onjuist.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_minutes = getattr(settings, "jwt_expire_minutes", 480)

    access_token = create_access_token(
        subject=request.username,
        secret_key=settings.secret_key,
        expires_minutes=expire_minutes,
    )
    refresh_token = create_refresh_token(
        subject=request.username,
        secret_key=settings.secret_key,
    )

    logger.info("Successful login: %s", request.username)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expire_minutes * 60,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    settings=Depends(_get_settings),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access token.

    Refresh tokens are valid for 7 days. Use this to avoid re-login.
    """
    try:
        payload = decode_token(request.refresh_token, settings.secret_key)
        subject: Optional[str] = payload.get("sub")
        token_type: str = payload.get("type", "")

        if not subject or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Ongeldig refresh token.",
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token verlopen of ongeldig. Log opnieuw in.",
        ) from exc

    expire_minutes = getattr(settings, "jwt_expire_minutes", 480)

    new_access_token = create_access_token(
        subject=subject,
        secret_key=settings.secret_key,
        expires_minutes=expire_minutes,
    )
    new_refresh_token = create_refresh_token(
        subject=subject,
        secret_key=settings.secret_key,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=expire_minutes * 60,
    )


@auth_router.get("/me", response_model=MeResponse)
async def get_me(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    settings=Depends(_get_settings),
) -> MeResponse:
    """
    Return info about the currently authenticated user.

    Returns 401 if no valid token is provided.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niet ingelogd.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, settings.secret_key)
        subject = payload.get("sub", "unknown")
        return MeResponse(username=subject, authenticated=True)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ongeldig.",
        ) from exc
