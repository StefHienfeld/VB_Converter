"""
FastAPI application exposing the Hienfeld VB Converter analysis pipeline.

This API is intended to be consumed by the React/Vite frontend from the
floating-glass-converter project.

Main responsibilities:
- Accept uploads (polisbestand, voorwaarden, clausulebibliotheek)
- Run the complete analysis pipeline in a background job
- Expose status/progress information
- Return structured results and an Excel rapport for download

Architecture (v4.3 - MVC refactoring):
- Orchestrator pattern: AnalysisOrchestrator coordinates the pipeline
- Factory pattern: ServiceFactory creates and configures services
- Repository pattern: MemoryJobRepository stores job state

Run locally (example):

    uvicorn hienfeld_api.app:app --reload --port 8000
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from hienfeld.config import load_config
from hienfeld.settings import get_settings

# Import models from MVC structure
from hienfeld_api.models import (
    AnalysisJob,
    JobStatus,
    StartAnalysisResponse,
    JobStatusResponse,
    AnalysisResultRowModel,
    AnalysisResultsResponse,
    UploadPreviewResponse,
)
from hienfeld_api.repositories import MemoryJobRepository
from hienfeld_api.middleware import setup_security
from hienfeld_api.routes import health_router
from hienfeld_api.orchestrators import AnalysisOrchestrator, AnalysisInput
from hienfeld_api.factories import ServiceFactory

from hienfeld.logging_config import get_logger, setup_logging
from hienfeld.services.service_cache import get_service_cache
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.services.custom_instructions_service import CustomInstructionsService

# ---------------------------------------------------------------------------
# Logging & app setup
# ---------------------------------------------------------------------------

setup_logging()
logger = get_logger("api")

# Integrate with uvicorn's logging so all logs appear in terminal
try:
    uvicorn_logger = logging.getLogger("uvicorn")
    # Share handlers with uvicorn so logs appear in same output
    if uvicorn_logger.handlers:
        logger.handlers = uvicorn_logger.handlers
        logger.setLevel(uvicorn_logger.level or logging.INFO)
except Exception:
    # If uvicorn logger not available, continue with default logging
    pass

# Load environment settings
settings = get_settings()

# Create shared orchestrator instance
service_factory = ServiceFactory()
orchestrator = AnalysisOrchestrator(service_factory=service_factory)

app = FastAPI(
    title="Hienfeld VB Converter API",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS - origins loaded from environment variable ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security middleware (headers, logging, rate limiting)
setup_security(app)

# Health check routes (for Docker/K8s)
app.include_router(health_router, prefix="/api")


# ---------------------------------------------------------------------------
# Job storage (Repository pattern)
# ---------------------------------------------------------------------------

job_repository = MemoryJobRepository()


# ---------------------------------------------------------------------------
# Core analysis function (background job)
# ---------------------------------------------------------------------------


def _run_analysis_job(
    job_id: str,
    policy_bytes: bytes,
    policy_filename: str,
    conditions_files: List[tuple[bytes, str]],
    clause_library_files: List[tuple[bytes, str]],
    reference_file: Optional[tuple[bytes, str]],
    settings: Dict[str, Any],
) -> None:
    """
    Run the complete analysis pipeline for a single job.

    Delegates to the AnalysisOrchestrator which coordinates all services
    and pipeline phases. This function is a thin wrapper that retrieves
    the job and prepares the input data.

    Architecture (v4.3):
    - AnalysisOrchestrator: Coordinates 8 pipeline phases
    - ServiceFactory: Creates and configures services
    - ServiceContainer: Holds all service instances
    """
    job = job_repository.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found when starting analysis")
        return

    # Create input data object
    input_data = AnalysisInput(
        policy_bytes=policy_bytes,
        policy_filename=policy_filename,
        conditions_files=conditions_files,
        clause_library_files=clause_library_files,
        reference_file=reference_file,
        settings=settings,
    )

    # Delegate to orchestrator
    orchestrator.run(job, input_data)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.post("/api/upload/preview", response_model=UploadPreviewResponse)
async def upload_preview(policy_file: UploadFile = File(...)) -> UploadPreviewResponse:
    """
    Optional helper endpoint:
    - Accept a polisbestand
    - Returns detected text/polis-nummer columns and simple stats
    """
    file_bytes = await policy_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Leeg bestand ontvangen")

    config = load_config()
    ingestion = IngestionService(config)
    df = ingestion.load_policy_file(file_bytes, policy_file.filename)
    info = ingestion.get_column_info(df)

    return UploadPreviewResponse(
        columns=list(info.get("columns", [])),
        row_count=int(info.get("row_count", 0)),
        text_column=str(info.get("text_column")),
        policy_column=info.get("policy_column"),
    )


@app.post("/api/analyze", response_model=StartAnalysisResponse)
async def start_analysis(
    background_tasks: BackgroundTasks,
    policy_file: UploadFile = File(...),
    conditions_files: List[UploadFile] = File(default=[]),
    clause_library_files: List[UploadFile] = File(default=[]),
    reference_file: Optional[UploadFile] = File(default=None),
    cluster_accuracy: int = Form(90),
    min_frequency: int = Form(20),
    window_size: int = Form(100),
    use_conditions: bool = Form(True),
    use_window_limit: bool = Form(True),
    use_semantic: bool = Form(True),
    ai_enabled: bool = Form(False),  # reserved for future AI extensions
    analysis_mode: str = Form("balanced"),  # fast, balanced, or accurate
    extra_instruction: str = Form(""),
) -> StartAnalysisResponse:
    """
    Start a new analysis job.

    This endpoint:
    - Validates and reads uploaded files
    - Creates a background job
    - Immediately returns a job_id
    """
    policy_bytes = await policy_file.read()
    if not policy_bytes:
        raise HTTPException(status_code=400, detail="Polisbestand is leeg of ontbreekt")

    conditions_data: List[tuple[bytes, str]] = []
    for f in conditions_files:
        data = await f.read()
        if data:
            conditions_data.append((data, f.filename))

    clause_data: List[tuple[bytes, str]] = []
    for f in clause_library_files:
        data = await f.read()
        if data:
            clause_data.append((data, f.filename))

    # Read reference file (optional - for yearly vs monthly comparison)
    reference_data: Optional[tuple[bytes, str]] = None
    if reference_file:
        ref_bytes = await reference_file.read()
        if ref_bytes:
            reference_data = (ref_bytes, reference_file.filename)
            logger.info(f"Reference file uploaded: {reference_file.filename}")

    job_id = str(uuid.uuid4())
    job = AnalysisJob(id=job_id)
    job_repository.save(job)

    settings = {
        "cluster_accuracy": cluster_accuracy,
        "min_frequency": min_frequency,
        "window_size": window_size,
        "use_conditions": use_conditions,
        "use_window_limit": use_window_limit,
        "use_semantic": use_semantic,
        "ai_enabled": ai_enabled,
        "analysis_mode": analysis_mode,
        "extra_instruction": extra_instruction,
    }

    background_tasks.add_task(
        _run_analysis_job,
        job_id,
        policy_bytes,
        policy_file.filename,
        conditions_data,
        clause_data,
        reference_data,
        settings,
    )

    logger.info(
        "Started analysis job %s for file %s (rows/settings will be logged in background)",
        job_id,
        policy_file.filename,
    )
    return StartAnalysisResponse(job_id=job_id, status=job.status)


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str) -> JobStatusResponse:
    """Return status/progress for a given analysis job."""
    job = job_repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job niet gevonden")

    stats = job.stats if job.status == JobStatus.COMPLETED else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        status_message=job.status_message,
        error=job.error,
        stats=stats,
    )


@app.get("/api/results/{job_id}", response_model=AnalysisResultsResponse)
async def get_results(job_id: str) -> AnalysisResultsResponse:
    """
    Return full analysis results for a completed job.

    If the job has not completed yet, returns HTTP 202.
    """
    job = job_repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job niet gevonden")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=202,
            detail=f"Job status is '{job.status}', resultaten nog niet beschikbaar",
        )

    if job.results is None or job.stats is None:
        raise HTTPException(status_code=500, detail="Resultaten ontbreken voor deze job")

    rows = [AnalysisResultRowModel(**row) for row in job.results]
    return AnalysisResultsResponse(
        job_id=job.id,
        status=job.status,
        stats=job.stats,
        results=rows,
    )


@app.get("/api/report/{job_id}")
async def download_report(job_id: str) -> StreamingResponse:
    """
    Download the Excel rapport for a completed job.
    """
    job = job_repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job niet gevonden")

    if job.status != JobStatus.COMPLETED or not job.excel_bytes:
        raise HTTPException(status_code=400, detail="Rapport nog niet beschikbaar")

    filename = job.excel_filename or "Hienfeld_Analyse.xlsx"

    return StreamingResponse(
        iter([job.excel_bytes]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Health endpoints moved to routes.py (health_router)


@app.post("/api/test-custom-instructions")
def test_custom_instructions(
    instructions_text: str = Form(...),
    test_clause: str = Form(...)
):
    """
    Test endpoint for debugging custom instructions matching.
    
    This endpoint allows you to test if custom instructions are being
    parsed and matched correctly without running a full analysis.
    
    Args:
        instructions_text: Raw custom instructions (TSV or arrow format)
        test_clause: Sample clause text to test matching against
        
    Returns:
        Detailed diagnostics about parsing and matching
    """
    try:
        # Initialize services
        base_similarity = RapidFuzzSimilarityService(threshold=0.65)
        
        # Create custom instructions service
        custom_service = CustomInstructionsService(
            fuzzy_service=base_similarity,
            semantic_service=None,  # Not needed for basic testing
            hybrid_service=None
        )
        
        # Load instructions
        loaded_count = custom_service.load_instructions(instructions_text)
        
        # Get loaded instructions
        instructions_list = [
            {
                "search_text": instr.search_text,
                "action": instr.action,
                "original": instr.original_text
            }
            for instr in custom_service.instructions
        ]
        
        # Test matching
        match_result = custom_service.find_match(test_clause)
        
        # Build response
        response = {
            "success": True,
            "input": {
                "instructions_text": instructions_text,
                "instructions_text_length": len(instructions_text),
                "test_clause": test_clause,
                "test_clause_length": len(test_clause)
            },
            "parsed": {
                "count": loaded_count,
                "instructions": instructions_list
            },
            "matching": {
                "found_match": match_result is not None,
                "match_details": None if match_result is None else {
                    "search_text": match_result.instruction.search_text,
                    "action": match_result.instruction.action,
                    "score": match_result.score,
                    "matched_text": match_result.matched_text[:100] + "..." if len(match_result.matched_text) > 100 else match_result.matched_text
                }
            },
            "diagnostics": {
                "contains_check": [],
                "test_clause_normalized": test_clause.casefold()[:100] + "..." if len(test_clause) > 100 else test_clause.casefold()
            }
        }
        
        # Manual contains check for diagnostics
        for instr in custom_service.instructions:
            needle = instr.search_text.casefold()
            haystack = test_clause.casefold()
            found = needle in haystack
            response["diagnostics"]["contains_check"].append({
                "search_text": instr.search_text,
                "search_text_normalized": needle,
                "found_in_clause": found,
                "explanation": f"'{needle}' {'IS' if found else 'NOT'} in '{haystack[:50]}...'"
            })
        
        return response
        
    except Exception as e:
        logger.error(f"Test custom instructions error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


# ---------------------------------------------------------------------------
# Cache management endpoints
# ---------------------------------------------------------------------------


@app.get("/api/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    Get service cache statistics.

    Returns cache metadata including:
    - Total cached entries
    - Access counts per service
    - Age of cached services
    - Last access times

    Useful for monitoring cache performance and debugging.
    """
    cache = get_service_cache()
    return cache.get_stats()


@app.post("/api/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """
    Clear entire service cache.

    Forces all services (NLP, embeddings, etc.) to reload on next request.
    Useful for:
    - Testing
    - Forcing model updates
    - Debugging memory issues

    Returns:
        Number of cleared entries
    """
    cache = get_service_cache()
    count = cache.clear()
    logger.info(f"🗑️  Cache cleared via API ({count} entries)")
    return {
        "status": "ok",
        "message": f"Cleared {count} cached services",
        "cleared_count": count
    }


@app.delete("/api/cache/{key}")
async def invalidate_cache_entry(key: str) -> Dict[str, Any]:
    """
    Invalidate specific cache entry.

    Args:
        key: Cache key (e.g., 'nlp_service_nl_core_news_md')

    Returns:
        Success status
    """
    cache = get_service_cache()
    success = cache.invalidate(key)
    if success:
        logger.info(f"🗑️  Cache entry '{key}' invalidated via API")
        return {
            "status": "ok",
            "message": f"Invalidated '{key}'"
        }
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Cache key '{key}' not found"
        )


