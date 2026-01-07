# hienfeld_api/routes.py
"""
Health check routes for Docker/Kubernetes probes.
"""
import os
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter
import spacy

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def healthcheck() -> Dict[str, Any]:
    """
    Main health endpoint for monitoring.
    Returns status, version, environment and timestamp.
    """
    return {
        "status": "healthy",
        "version": os.environ.get("APP_VERSION", "4.2.0"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@health_router.get("/health/live")
async def liveness() -> Dict[str, str]:
    """
    Kubernetes liveness probe.
    Returns alive if the service is running.
    """
    return {"status": "alive"}


@health_router.get("/health/ready")
async def readiness() -> Dict[str, Any]:
    """
    Kubernetes readiness probe.
    Checks if all dependencies are ready.
    """
    checks = {}
    all_ready = True

    # Check SpaCy model
    try:
        nlp = spacy.load("nl_core_news_md")
        checks["spacy_model"] = {"status": "ok", "model": "nl_core_news_md"}
    except Exception as e:
        checks["spacy_model"] = {"status": "error", "message": str(e)}
        all_ready = False

    return {
        "status": "ready" if all_ready else "degraded",
        "checks": checks
    }
