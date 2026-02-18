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
- Repository pattern: SQLJobRepository (SQLite default) stores job state persistently

Run locally (example):

    uvicorn hienfeld_api.app:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

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
from hienfeld_api.repositories import MemoryJobRepository, SQLJobRepository
from hienfeld_api.middleware import setup_security, limiter
from hienfeld_api.routes import health_router
from hienfeld_api.routes.auth import auth_router
from hienfeld_api.auth import get_current_user_dependency
from hienfeld_api.orchestrators import AnalysisOrchestrator, AnalysisInput
from hienfeld_api.factories import ServiceFactory
from hienfeld_api.validation import validate_file_upload, validate_analysis_settings
from hienfeld_api.models import FileUploadLimits, AnalysisSettings

from hienfeld.logging_config import get_logger, setup_logging
from hienfeld.services.service_cache import get_service_cache
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.services.custom_instructions_service import CustomInstructionsService
from hienfeld_api.audit_service import AuditService

# Prometheus metrics
from hienfeld_api.metrics import (
    get_metrics,
    get_content_type,
    record_analysis_start,
    record_analysis_complete,
    record_analysis_error,
    active_jobs,
)

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

# ---------------------------------------------------------------------------
# Job repository (declared early so lifespan can access it)
# ---------------------------------------------------------------------------


def _create_job_repository():
    """
    Create the job repository based on environment configuration.

    Priority:
    1. POSTGRES_URL  → SQLJobRepository (PostgreSQL, persistent)
    2. SQLITE_URL    → SQLJobRepository (SQLite, persistent local dev)
    3. DATABASE_URL  → SQLJobRepository (unified URL; default: SQLite file)
    4. None          → MemoryJobRepository (in-memory, no persistence)

    DATABASE_URL defaults to sqlite:///./hienfeld_jobs.db so jobs survive
    server restarts without any extra configuration.

    Also stores the session factory globally so AuditService can use it.
    """
    global _db_session_factory
    from hienfeld_api.database import Base, create_db_engine, create_session_factory

    db_url = settings.postgres_url or settings.sqlite_url or settings.database_url
    if db_url:
        try:
            engine = create_db_engine(db_url)
            # Create tables if they don't exist (Alembic handles migrations in production)
            Base.metadata.create_all(bind=engine)
            session_factory = create_session_factory(engine)
            _db_session_factory = session_factory
            repo = SQLJobRepository(session_factory)
            db_type = "PostgreSQL" if "postgresql" in db_url else "SQLite"
            logger.info("Job repository: %s (%s)", db_type, db_url.split("@")[-1] if "@" in db_url else db_url)
            return repo
        except Exception as exc:
            logger.warning(
                "Could not connect to database (%s) — falling back to in-memory storage: %s",
                db_url.split("@")[-1] if "@" in db_url else db_url,
                exc,
            )

    logger.info("Job repository: in-memory (jobs lost on restart)")
    return MemoryJobRepository()


_db_session_factory = None
job_repository = _create_job_repository()
audit_service = AuditService(session_factory=_db_session_factory)

# ---------------------------------------------------------------------------
# GDPR background cleanup task (every 30 min, removes jobs > 24h old)
# ---------------------------------------------------------------------------

_cleanup_task: Optional[asyncio.Task] = None
_CLEANUP_INTERVAL_SECONDS = 30 * 60  # 30 minutes


async def _periodic_job_cleanup() -> None:
    """Background task: clean up expired jobs every 30 minutes for GDPR compliance."""
    while True:
        try:
            await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
            deleted = job_repository.cleanup_expired_jobs()
            if deleted:
                logger.info("Periodic GDPR cleanup: deleted %d expired jobs", deleted)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in periodic job cleanup: %s", exc, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_periodic_job_cleanup())
    logger.info("GDPR job cleanup task started (interval: 30 min, TTL: 24h)")
    yield
    if _cleanup_task:
        _cleanup_task.cancel()
        logger.info("GDPR job cleanup task stopped")


app = FastAPI(
    title="Hienfeld VB Converter API",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS - origins loaded from environment variable ALLOWED_ORIGINS
_allowed_origins = settings.get_allowed_origins_list()
if settings.is_production:
    _localhost_origins = [o for o in _allowed_origins if "localhost" in o or "127.0.0.1" in o]
    if _localhost_origins:
        logger.warning(
            "CORS WARNING: localhost origins are allowed in production! "
            "Remove from ALLOWED_ORIGINS: %s",
            ", ".join(_localhost_origins),
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Security middleware (headers, logging, rate limiting)
setup_security(app)

# Auth router (public — no JWT required to log in)
app.include_router(auth_router, prefix="/api")

# JWT dependency — applied to all /api/* routes EXCEPT /auth/* and /health*
_require_auth = get_current_user_dependency(settings)

# Health check routes (for Docker/K8s) — public, no auth
app.include_router(health_router, prefix="/api")

if settings.auth_enabled:
    logger.info("JWT authentication ENABLED (AUTH_ENABLED=true)")


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

    # Delegate to orchestrator and record audit log on completion/failure
    start_time = time.monotonic()
    analysis_mode = settings.get("analysis_mode", "balanced")

    # Record metrics: analysis started
    record_analysis_start()

    try:
        orchestrator.run(job, input_data)
        duration = time.monotonic() - start_time
        refreshed = job_repository.get(job_id)
        if refreshed and refreshed.status == JobStatus.COMPLETED:
            audit_service.log_analysis_completed(job_id, "system", int(duration), analysis_mode)
            # Record metrics: analysis completed
            row_count = refreshed.stats.get("total_rows", 0) if refreshed.stats else 0
            record_analysis_complete(duration, analysis_mode, row_count)
        else:
            audit_service.log_analysis_failed(job_id, "system", int(duration), analysis_mode)
            record_analysis_error("processing")
    except Exception as exc:
        duration = time.monotonic() - start_time
        audit_service.log_analysis_failed(job_id, "system", int(duration), analysis_mode)
        # Record metrics: analysis error
        error_type = "timeout" if "timeout" in str(exc).lower() else "processing"
        record_analysis_error(error_type)
        raise


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.post("/api/upload/preview", response_model=UploadPreviewResponse)
async def upload_preview(
    policy_file: UploadFile = File(...),
    _current_user: str = Depends(_require_auth),
) -> UploadPreviewResponse:
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
@limiter.limit("10/minute")
async def start_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    _current_user: str = Depends(_require_auth),
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
    - Validates and reads uploaded files (size, type, extension)
    - Validates analysis settings (range checks)
    - Creates a background job
    - Immediately returns a job_id
    """
    upload_limits = FileUploadLimits()

    # Validate and read policy file (required)
    policy_bytes, policy_filename = await validate_file_upload(policy_file, upload_limits)

    conditions_data: List[tuple[bytes, str]] = []
    for f in conditions_files:
        try:
            data, fname = await validate_file_upload(f, upload_limits)
            conditions_data.append((data, fname))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Voorwaardenbestand ongeldig: {exc}") from exc

    clause_data: List[tuple[bytes, str]] = []
    for f in clause_library_files:
        try:
            data, fname = await validate_file_upload(f, upload_limits)
            clause_data.append((data, fname))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Clausulebibliotheek ongeldig: {exc}") from exc

    # Read reference file (optional)
    reference_data: Optional[tuple[bytes, str]] = None
    if reference_file:
        try:
            ref_bytes, ref_name = await validate_file_upload(reference_file, upload_limits)
            reference_data = (ref_bytes, ref_name)
            logger.info("Reference file uploaded: %s", ref_name)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Referentiebestand ongeldig: {exc}") from exc

    # Validate analysis settings (range + allowed values)
    raw_settings = {
        "cluster_accuracy": cluster_accuracy,
        "min_frequency": min_frequency,
        "window_size": window_size,
        "analysis_mode": analysis_mode,
        "extra_instruction": extra_instruction,
    }
    validated = validate_analysis_settings(raw_settings)

    job_id = str(uuid.uuid4())
    job = AnalysisJob(id=job_id)
    job_repository.save(job)

    # GDPR audit: log analysis start (filenames only, no content)
    all_file_names = [policy_filename]
    all_file_names += [fname for _, fname in conditions_data]
    all_file_names += [fname for _, fname in clause_data]
    if reference_data:
        all_file_names.append(reference_data[1])
    audit_service.log_analysis_started(
        job_id=job_id,
        user_id=_current_user,
        file_names=all_file_names,
        analysis_mode=analysis_mode,
    )

    settings = {
        "cluster_accuracy": validated["cluster_accuracy"],
        "min_frequency": validated["min_frequency"],
        "window_size": validated["window_size"],
        "use_conditions": use_conditions,
        "use_window_limit": use_window_limit,
        "use_semantic": use_semantic,
        "ai_enabled": ai_enabled,
        "analysis_mode": validated["analysis_mode"],
        "extra_instruction": validated["extra_instruction"],
    }

    background_tasks.add_task(
        _run_analysis_job,
        job_id,
        policy_bytes,
        policy_filename,
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
async def get_status(
    job_id: str,
    _current_user: str = Depends(_require_auth),
) -> JobStatusResponse:
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
async def get_results(
    job_id: str,
    _current_user: str = Depends(_require_auth),
) -> AnalysisResultsResponse:
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
async def download_report(
    job_id: str,
    _current_user: str = Depends(_require_auth),
) -> StreamingResponse:
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
    test_clause: str = Form(...),
    _current_user: str = Depends(_require_auth),
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
async def get_cache_stats(
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
    """
    Get service cache statistics.

    Returns cache metadata including:
    - Total cached entries
    - Access counts per service
    - Age of cached services
    - Last access times
    - Policy embeddings cache stats (v4.4)

    Useful for monitoring cache performance and debugging.
    """
    cache = get_service_cache()
    stats = cache.get_stats()

    # Include policy embeddings cache stats (v4.4)
    try:
        from hienfeld.services.ai.policy_embeddings_cache import get_policy_embeddings_cache
        embeddings_cache = get_policy_embeddings_cache()
        stats['policy_embeddings_cache'] = embeddings_cache.get_statistics()
    except Exception as e:
        stats['policy_embeddings_cache'] = {'error': str(e)}

    return stats


@app.post("/api/cache/clear")
async def clear_cache(
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
    """
    Clear entire service cache.

    Forces all services (NLP, embeddings, etc.) to reload on next request.
    Also clears the policy embeddings cache (v4.4).

    Useful for:
    - Testing
    - Forcing model updates
    - Debugging memory issues

    Returns:
        Number of cleared entries
    """
    cache = get_service_cache()
    count = cache.clear()

    # Also clear policy embeddings cache (v4.4)
    embeddings_count = 0
    try:
        from hienfeld.services.ai.policy_embeddings_cache import get_policy_embeddings_cache
        embeddings_cache = get_policy_embeddings_cache()
        embeddings_count = embeddings_cache.clear()
    except Exception:
        pass

    total_count = count + embeddings_count
    logger.info(f"Cache cleared via API ({count} services, {embeddings_count} embeddings)")
    return {
        "status": "ok",
        "message": f"Cleared {count} services, {embeddings_count} embeddings",
        "cleared_count": total_count,
        "services_cleared": count,
        "embeddings_cleared": embeddings_count
    }


@app.delete("/api/cache/{key}")
async def invalidate_cache_entry(
    key: str,
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Policy Embeddings Cache endpoints (v4.4)
# ---------------------------------------------------------------------------


@app.get("/api/cache/embeddings/stats")
async def get_embeddings_cache_stats(
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
    """
    Get policy embeddings cache statistics (v4.4).

    Returns:
    - Number of cached documents
    - Cache hit/miss rates
    - Total time saved (estimated)
    - Memory usage

    This cache avoids recomputing embeddings for policy documents
    that have been analyzed before, saving ~20-30 seconds per analysis.
    """
    try:
        from hienfeld.services.ai.policy_embeddings_cache import get_policy_embeddings_cache
        embeddings_cache = get_policy_embeddings_cache()
        return embeddings_cache.get_statistics()
    except Exception as e:
        logger.error(f"Error getting embeddings cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not get embeddings cache stats: {e}"
        )


@app.post("/api/cache/embeddings/clear")
async def clear_embeddings_cache(
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
    """
    Clear policy embeddings cache (v4.4).

    Forces re-computation of embeddings on next analysis.
    Useful when testing or debugging embedding issues.

    Returns:
        Number of entries cleared
    """
    try:
        from hienfeld.services.ai.policy_embeddings_cache import get_policy_embeddings_cache
        embeddings_cache = get_policy_embeddings_cache()
        count = embeddings_cache.clear()
        logger.info(f"Policy embeddings cache cleared via API ({count} entries)")
        return {
            "status": "ok",
            "message": f"Cleared {count} cached embedding entries",
            "cleared_count": count
        }
    except Exception as e:
        logger.error(f"Error clearing embeddings cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not clear embeddings cache: {e}"
        )


# ---------------------------------------------------------------------------
# GDPR: manual job cleanup endpoint
# ---------------------------------------------------------------------------


@app.post("/api/jobs/cleanup")
async def trigger_job_cleanup(
    _current_user: str = Depends(_require_auth),
) -> Dict[str, Any]:
    """
    Manually trigger GDPR job cleanup.

    Deletes all jobs older than 24 hours (TTL policy).
    Normally runs automatically every 30 minutes.
    """
    deleted = job_repository.cleanup_expired_jobs()
    remaining = job_repository.job_count
    logger.info("Manual GDPR cleanup: %d jobs deleted, %d remaining", deleted, remaining)
    return {
        "status": "ok",
        "deleted": deleted,
        "remaining": remaining,
        "ttl_hours": 24,
    }


# ---------------------------------------------------------------------------
# Prometheus Metrics Endpoint
# ---------------------------------------------------------------------------


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint(request: Request) -> Response:
    """
    Expose Prometheus metrics for scraping.

    Access is restricted to:
    1. Requests originating from localhost (127.0.0.1 / ::1), OR
    2. Requests that supply a valid METRICS_TOKEN in the Authorization header
       (format: 'Bearer <token>'  or just the token as a raw value).

    Configure METRICS_TOKEN via environment variable. If not set, only
    localhost access is permitted.

    Returns metrics in Prometheus exposition format.
    """
    # Determine the client IP, respecting X-Forwarded-For from trusted proxies.
    client_host = request.client.host if request.client else ""
    is_localhost = client_host in ("127.0.0.1", "::1", "localhost")

    # Check for optional METRICS_TOKEN (allows Prometheus running off-host)
    expected_token: str = getattr(settings, "metrics_token", "") or ""
    if expected_token:
        auth_header = request.headers.get("Authorization", "")
        # Accept both 'Bearer <token>' and bare token value
        provided_token = auth_header.removeprefix("Bearer ").strip()
        token_valid = provided_token == expected_token
    else:
        token_valid = False

    if not is_localhost and not token_valid:
        logger.warning(
            "Metrics endpoint access denied for host '%s' (no valid token, not localhost)",
            client_host,
        )
        raise HTTPException(
            status_code=403,
            detail="Metrics endpoint is only accessible from localhost or with a valid METRICS_TOKEN.",
        )

    # Update active jobs gauge before returning metrics
    try:
        active_jobs.set(job_repository.job_count)
    except Exception:
        pass  # Don't fail metrics if job count fails

    return Response(
        content=get_metrics(),
        media_type=get_content_type(),
    )
