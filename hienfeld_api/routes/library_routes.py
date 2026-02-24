"""
API routes for product library management.

Provides CRUD operations and build process for product libraries.
Auth is applied at router level when included in app.py.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from hienfeld.logging_config import get_logger
from hienfeld.services.library_service import LibraryService
from hienfeld_api.validation import validate_file_upload
from hienfeld_api.models import FileUploadLimits

logger = get_logger("library_routes")

library_router = APIRouter(tags=["libraries"])

# Module-level state set by init_library_routes()
_library_service: Optional[LibraryService] = None


def init_library_routes(library_service: LibraryService):
    """Initialize library routes with dependencies. Called from app startup."""
    global _library_service
    _library_service = library_service


def _get_service() -> LibraryService:
    """Dependency: return the initialized LibraryService or raise 503."""
    if _library_service is None:
        raise HTTPException(status_code=503, detail="Library service niet beschikbaar")
    return _library_service


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@library_router.post("/libraries")
async def create_library(
    naam: str = Form(...),
    verzekeraar: Optional[str] = Form(None),
    versie: Optional[str] = Form(None),
    beschrijving: Optional[str] = Form(None),
    service: LibraryService = Depends(_get_service),
):
    """Create a new product library in draft status."""
    try:
        return service.create_library(
            naam=naam,
            verzekeraar=verzekeraar,
            versie=versie,
            beschrijving=beschrijving,
            aangemaakt_door="system",
        )
    except Exception as e:
        logger.error("Failed to create library: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/libraries")
async def list_libraries(
    status: Optional[str] = None,
    service: LibraryService = Depends(_get_service),
):
    """List all libraries, optionally filtered by status."""
    return service.list_libraries(status_filter=status)


@library_router.get("/libraries/{library_id}")
async def get_library(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Get a single library by ID."""
    result = service.get_library(library_id)
    if not result:
        raise HTTPException(status_code=404, detail="Bibliotheek niet gevonden")
    return result


@library_router.get("/libraries/{library_id}/build-status")
async def get_build_status(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Get build progress for a library (for polling during build)."""
    result = service.get_build_status(library_id)
    if not result:
        raise HTTPException(status_code=404, detail="Bibliotheek niet gevonden")
    return result


# ---------------------------------------------------------------------------
# Build endpoint
# ---------------------------------------------------------------------------


@library_router.post("/libraries/{library_id}/build")
async def build_library(
    library_id: str,
    background_tasks: BackgroundTasks,
    conditions_files: List[UploadFile] = File(default=[]),
    clause_files: List[UploadFile] = File(default=[]),
    service: LibraryService = Depends(_get_service),
):
    """Start building a library (background task)."""
    library = service.get_library(library_id)
    if not library:
        raise HTTPException(status_code=404, detail="Bibliotheek niet gevonden")

    upload_limits = FileUploadLimits()

    conditions_data = []
    for f in conditions_files:
        data, fname = await validate_file_upload(f, upload_limits)
        conditions_data.append((data, fname))

    clause_data = []
    for f in clause_files:
        data, fname = await validate_file_upload(f, upload_limits)
        clause_data.append((data, fname))

    if not conditions_data and not clause_data:
        raise HTTPException(
            status_code=400,
            detail="Upload ten minste een voorwaarden- of clausulebestand",
        )

    background_tasks.add_task(_run_library_build, library_id, conditions_data, clause_data)
    return {"status": "building", "message": "Build gestart..."}


def _run_library_build(library_id: str, conditions_data: list, clause_data: list):
    """Background task that assembles services and runs the build pipeline."""
    service = _get_service()
    embeddings_service = None
    policy_parser = None
    clause_library_service = None

    try:
        from hienfeld.config import load_config

        config = load_config()

        from hienfeld.services.policy_parser_service import PolicyParserService

        policy_parser = PolicyParserService(config)

        # Embeddings (optional - may not be available in dev)
        try:
            from hienfeld.services.ai.embeddings_service import SentenceTransformerEmbeddingsService
            from hienfeld.services.service_cache import get_service_cache

            cache = get_service_cache()
            embeddings_service = cache.get_or_create(
                "embeddings_service",
                lambda: SentenceTransformerEmbeddingsService(config),
                ttl=3600,
            )
        except Exception as e:
            logger.warning("Embeddings service not available: %s", e)

        # Clause library (for CSV/Excel clause files)
        if clause_data:
            from hienfeld.services.clause_library_service import ClauseLibraryService
            from hienfeld.services.similarity_service import RapidFuzzSimilarityService

            clause_library_service = ClauseLibraryService(
                config, similarity_service=RapidFuzzSimilarityService(threshold=0.90)
            )

        service.build_library(
            library_id=library_id,
            conditions_files=conditions_data,
            clause_files=clause_data,
            embeddings_service=embeddings_service,
            policy_parser=policy_parser,
            clause_library_service=clause_library_service,
        )
    except Exception as e:
        logger.error("Library build background task failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Management endpoints
# ---------------------------------------------------------------------------


@library_router.post("/libraries/{library_id}/archive")
async def archive_library(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Archive a library (set status to archived)."""
    success = service.archive_library(library_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bibliotheek niet gevonden")
    return {"status": "ok", "message": "Bibliotheek gearchiveerd"}


@library_router.delete("/libraries/{library_id}")
async def delete_library(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Delete a draft library."""
    try:
        success = service.delete_library(library_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bibliotheek niet gevonden")
        return {"status": "ok", "message": "Bibliotheek verwijderd"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@library_router.get("/libraries/{library_id}/sections")
async def get_sections(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Get all sections for a library (ruwe_tekst truncated to 500 chars)."""
    return service.get_sections(library_id)


@library_router.get("/libraries/{library_id}/clauses")
async def get_clauses(
    library_id: str,
    service: LibraryService = Depends(_get_service),
):
    """Get all clauses for a library (tekst truncated to 300 chars)."""
    return service.get_clauses(library_id)
