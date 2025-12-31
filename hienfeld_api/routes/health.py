"""
Health check endpoints for monitoring and orchestration.

Provides:
- /health - Full health check with version info
- /health/live - Kubernetes liveness probe
- /health/ready - Kubernetes readiness probe
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from hienfeld.settings import get_settings

router = APIRouter(tags=["Health"])
settings = get_settings()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    status: str
    checks: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Full health check endpoint.

    Returns application status, version, and environment.
    Used by monitoring systems and load balancers.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=settings.app_version,
        environment=settings.environment.value,
    )


@router.get("/health/live")
async def liveness() -> Dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 if the application is alive.
    If this fails, Kubernetes will restart the container.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response) -> ReadinessResponse:
    """
    Kubernetes readiness probe.

    Checks if all dependencies are ready:
    - SpaCy model loaded
    - Other services available

    If this fails, Kubernetes will stop routing traffic to this pod.
    """
    checks = {}
    all_ready = True

    # Check SpaCy model
    try:
        import spacy
        nlp = spacy.load(settings.spacy_model)
        checks["spacy"] = {"status": "ready", "model": settings.spacy_model}
    except Exception as e:
        checks["spacy"] = {"status": "not_ready", "error": str(e)}
        all_ready = False

    # Overall status
    if not all_ready:
        response.status_code = 503

    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        checks=checks,
    )
