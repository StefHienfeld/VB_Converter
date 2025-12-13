"""
FastAPI application exposing the Hienfeld VB Converter analysis pipeline.

This API is intended to be consumed by the React/Vite frontend from the
floating-glass-converter project.

Main responsibilities:
- Accept uploads (polisbestand, voorwaarden, clausulebibliotheek)
- Run the complete analysis pipeline in a background job
- Expose status/progress information
- Return structured results and an Excel rapport for download

Run locally (example):

    uvicorn hienfeld_api.app:app --reload --port 8000
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hienfeld.config import load_config
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.logging_config import get_logger, setup_logging, log_section
from hienfeld.utils.timing import PhaseTimer, Timer
from hienfeld.services.service_cache import get_service_cache
from hienfeld.services.admin_check_service import AdminCheckService
from hienfeld.services.analysis_service import AnalysisService
from hienfeld.services.clause_library_service import ClauseLibraryService
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.export_service import ExportService
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.policy_parser_service import PolicyParserService
from hienfeld.services.preprocessing_service import PreprocessingService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService, SemanticSimilarityService
from hienfeld.services.document_similarity_service import DocumentSimilarityService
from hienfeld.services.ai.embeddings_service import create_embeddings_service
from hienfeld.services.ai.vector_store import create_vector_store
from hienfeld.services.ai.rag_service import RAGService
from hienfeld.services.ai.llm_analysis_service import LLMAnalysisService
from hienfeld.services.custom_instructions_service import CustomInstructionsService

# ---------------------------------------------------------------------------
# Logging & app setup
# ---------------------------------------------------------------------------

setup_logging()
logger = get_logger("api")

# Semantic enhancement services (v3.0 - optional)
try:
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False
    logger.info("Hybrid similarity service not available (install spacy, gensim, wn)")

app = FastAPI(title="Hienfeld VB Converter API", version="1.0.0")

# CORS so the Vite frontend (http://localhost:5173 by default) can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8082",
        "http://127.0.0.1:8082",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Internal job model
# ---------------------------------------------------------------------------


class JobStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AnalysisJob:
    id: str
    status: str = JobStatus.PENDING
    progress: int = 0
    status_message: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    stats: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None
    excel_bytes: Optional[bytes] = None
    excel_filename: Optional[str] = None


JOBS: Dict[str, AnalysisJob] = {}


def _update_job(
    job: AnalysisJob,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Helper to update a job safely."""
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = int(progress)
    if message is not None:
        job.status_message = message
    if error is not None:
        job.error = error


# ---------------------------------------------------------------------------
# Pydantic models for responses
# ---------------------------------------------------------------------------


class StartAnalysisResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    status_message: str
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class AnalysisResultRowModel(BaseModel):
    cluster_id: str
    cluster_name: str
    frequency: int
    advice_code: str
    confidence: str
    reason: str
    reference_article: str
    original_text: str
    row_type: str
    parent_id: Optional[str] = None


class AnalysisResultsResponse(BaseModel):
    job_id: str
    status: str
    stats: Optional[Dict[str, Any]]
    results: List[AnalysisResultRowModel]


class UploadPreviewResponse(BaseModel):
    columns: List[str]
    row_count: int
    text_column: str
    policy_column: Optional[str]


# ---------------------------------------------------------------------------
# Core analysis function (background job)
# ---------------------------------------------------------------------------


def _run_analysis_job(
    job_id: str,
    policy_bytes: bytes,
    policy_filename: str,
    conditions_files: List[tuple[bytes, str]],
    clause_library_files: List[tuple[bytes, str]],
    settings: Dict[str, Any],
) -> None:
    """
    Run the complete analysis pipeline for a single job.

    This mirrors the logic in `HienfeldState.run_analysis`, but operates
    without Reflex state and writes progress into the in-memory job.
    """
    job = JOBS.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found when starting analysis")
        return

    # Initialize phase timer for tracking entire pipeline
    phase_timer = PhaseTimer(f"Analysis Job {job_id[:8]}")

    try:
        _update_job(job, status=JobStatus.RUNNING, progress=0, message="Initialiseren...")

        log_section(logger, f"🚀 NEW ANALYSIS JOB: {job_id}")

        # Load base config and apply settings from the request
        config = load_config()

        # Apply analysis mode (FAST/BALANCED/ACCURATE)
        from hienfeld.config import AnalysisMode
        analysis_mode_str = settings.get("analysis_mode", "balanced")
        try:
            mode = AnalysisMode(analysis_mode_str)
            config.semantic.apply_mode(mode)
            logger.info(f"📊 Analysis mode: {mode.value.upper()}")
            logger.info(f"   • Time multiplier: {config.semantic.get_active_config().time_multiplier}x")
            logger.info(f"   • Cluster threshold: {settings.get('cluster_accuracy', 90)}%")
            logger.info(f"   • Min frequency: {settings.get('min_frequency', 20)}")
            logger.info(f"   • Window size: {settings.get('window_size', 100)}")
        except ValueError:
            logger.warning(f"Invalid analysis mode '{analysis_mode_str}', defaulting to BALANCED")
            mode = AnalysisMode.BALANCED
            config.semantic.apply_mode(mode)

        phase_timer.checkpoint("Configuration loaded")

        strictness_float = float(settings.get("cluster_accuracy", 90)) / 100.0
        min_freq = int(settings.get("min_frequency", 20))
        win_size = int(settings.get("window_size", 100))
        use_window_limit = bool(settings.get("use_window_limit", True))
        use_conditions = bool(settings.get("use_conditions", True))
        use_semantic = bool(settings.get("use_semantic", True))
        extra_instruction = str(settings.get("extra_instruction", "")).strip()

        config.clustering.similarity_threshold = strictness_float
        config.analysis_rules.frequency_standardize_threshold = min_freq
        config.clustering.leader_window_size = win_size if use_window_limit else 999999

        # Base similarity service for clustering (will be upgraded to hybrid if available)
        base_similarity_service = RapidFuzzSimilarityService(threshold=strictness_float)
        ingestion = IngestionService(config)
        preprocessing = PreprocessingService(config)
        policy_parser = PolicyParserService(config)

        # Initialize NLP service for semantic cluster naming (cached)
        nlp_service_for_naming = None
        if config.semantic.enabled and config.semantic.enable_nlp:
            try:
                from hienfeld.services.nlp_service import NLPService
                cache = get_service_cache()

                # Get or create cached NLP service
                nlp_service_for_naming = cache.get_or_create(
                    'nlp_service_nl_core_news_md',
                    lambda: NLPService(config),
                    ttl=None  # Cache indefinitely (model doesn't change)
                )

                if nlp_service_for_naming.is_available:
                    logger.info("✅ NLP service loaded for semantic cluster naming (cached)")
                else:
                    nlp_service_for_naming = None
            except Exception as e:
                logger.debug(f"NLP service not available for cluster naming: {e}")
                nlp_service_for_naming = None

        # Create clustering service - will use hybrid service later if available
        clustering = ClusteringService(
            config,
            similarity_service=base_similarity_service,
            nlp_service=nlp_service_for_naming
        )
        admin_check = AdminCheckService(config=config, llm_client=None, enable_ai_checks=False)
        export = ExportService(config)
        clause_library_service = ClauseLibraryService(config)
        tfidf_service = DocumentSimilarityService(config)
        semantic_service: Optional[SemanticSimilarityService] = None
        embeddings_service = None
        vector_store = None
        rag_service = None
        ai_analyzer = None
        
        hybrid_service = None

        # Step 1: Load policy file
        _update_job(job, progress=5, message="📄 Bestand inlezen...")
        logger.info(f"📄 Loading policy file: {policy_filename} ({len(policy_bytes)} bytes)")

        with Timer("Load policy file"):
            df = ingestion.load_policy_file(policy_bytes, policy_filename)
            text_col = ingestion.detect_text_column(df)
            policy_number_col = ingestion.detect_policy_number_column(df)

        logger.info(f"✅ Policy loaded: {len(df)} rows, text column: '{text_col}'")
        phase_timer.checkpoint(f"Policy file loaded ({len(df)} rows)")

        # Step 2: Parse conditions (if enabled)
        policy_sections: List[PolicyDocumentSection] = []
        if use_conditions and conditions_files:
            _update_job(job, progress=10, message="📚 Voorwaarden verwerken...")
            logger.info(f"📚 Parsing {len(conditions_files)} conditions files...")

            with Timer(f"Parse {len(conditions_files)} conditions files"):
                for file_bytes, filename in conditions_files:
                    try:
                        logger.debug(f"   • Parsing {filename} ({len(file_bytes)} bytes)...")
                        sections = policy_parser.parse_policy_file(file_bytes, filename)
                        policy_sections.extend(sections)
                        logger.debug(f"     → {len(sections)} sections extracted")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"Failed to parse {filename}: {exc}")

            logger.info(f"✅ Conditions parsed: {len(policy_sections)} total sections")
            phase_timer.checkpoint(f"Conditions parsed ({len(policy_sections)} sections)")
        else:
            _update_job(job, progress=10, message="📊 Modus: Interne analyse")
            logger.info("ℹ️  No conditions files - internal analysis mode")
            phase_timer.checkpoint("No conditions (internal mode)")

        # Initialize semantic stack (embeddings, RAG, TF-IDF) if requested and possible
        semantic_stack_active = False

        log_section(logger, "🧠 SEMANTIC SERVICES INITIALIZATION")

        # Initialize semantic services for clustering (independent of conditions)
        if use_semantic and config.semantic.enabled:
            # Train TF-IDF on voorwaarden (if available and we have conditions)
            if policy_sections and tfidf_service.is_available and config.semantic.enable_tfidf:
                _update_job(job, progress=12, message="🔤 TF-IDF model trainen...")
                logger.info("🔤 Training TF-IDF model...")

                with Timer("TF-IDF training"):
                    tfidf_corpus = [s.simplified_text for s in policy_sections if s.simplified_text]
                    if tfidf_corpus:
                        tfidf_service.train_on_corpus(tfidf_corpus)
                        logger.info(f"✅ TF-IDF trained on {len(tfidf_corpus)} documents")
                    else:
                        logger.warning("⚠️ No text in policy sections for TF-IDF training")

                phase_timer.checkpoint("TF-IDF training")

            # Embeddings + vector store (for clustering similarity) - cached
            if config.semantic.enable_embeddings:
                _update_job(job, progress=14, message="🧠 Embeddings laden...")
                try:
                    cache = get_service_cache()

                    # Get or create cached embeddings service
                    embeddings_service = cache.get_or_create(
                        f'embeddings_{config.semantic.embedding_model}',
                        lambda: create_embeddings_service(
                            model_name=config.semantic.embedding_model
                        ),
                        ttl=None  # Cache indefinitely (model doesn't change)
                    )

                    logger.info(f"✅ Embeddings service loaded (model: {config.semantic.embedding_model}, cached)")

                    _update_job(job, progress=16, message="📊 Vector store initialiseren...")
                    vector_store = create_vector_store(
                        method=config.ai.vector_store_type or "faiss",
                        embedding_dim=getattr(embeddings_service, "embedding_dim", 384),
                    )
                    _update_job(job, progress=18, message="🔍 RAG index bouwen...")
                    rag_service = RAGService(embeddings_service, vector_store)
                    rag_service.index_policy_sections(policy_sections)
                    logger.info("✅ RAG index opgebouwd voor semantische context")
                except ImportError as exc:
                    logger.warning(
                        "Embeddings/RAG niet geactiveerd: ontbrekende dependency (%s)", exc
                    )
                    embeddings_service = None
                    vector_store = None
                    rag_service = None
                except Exception as exc:
                    logger.warning("RAG initialisatie mislukt: %s", exc)
                    embeddings_service = None
                    vector_store = None
                    rag_service = None

            # Semantic similarity service (embedding-based)
            if embeddings_service is not None:
                semantic_service = SemanticSimilarityService(
                    embeddings_service=embeddings_service,
                    model_name=config.semantic.embedding_model,
                )
                if not semantic_service.is_available:
                    semantic_service = None

            # LLM analyzer (optional verification); only wire if a client is provided/enabled
            ai_enabled = bool(settings.get("ai_enabled")) and bool(config.ai.enabled)
            if ai_enabled:
                try:
                    ai_analyzer = LLMAnalysisService(
                        client=None,  # Plug real LLM client when API key/model configured
                        rag_service=rag_service,
                        model_name=config.ai.llm_model or "gpt-4",
                    )
                except Exception as exc:
                    logger.warning("LLM analyzer niet geactiveerd: %s", exc)
                    ai_analyzer = None

            semantic_stack_active = bool(semantic_service or rag_service or tfidf_service.is_trained)
        else:
            if not use_semantic:
                logger.info("Semantische analyse uitgeschakeld via verzoek")
            elif not policy_sections:
                logger.info("Geen voorwaarden geladen: semantische stap wordt overgeslagen")

        # Initialize hybrid similarity service (v3.0 semantic enhancement)
        if HYBRID_AVAILABLE and config.semantic.enabled and use_semantic:
            _update_job(job, progress=20, message="⚡ Hybrid similarity configureren...")
            try:
                # Get active mode configuration
                mode_config = config.semantic.get_active_config()

                # Enable embedding cache if configured
                if mode_config.use_embedding_cache and semantic_service:
                    semantic_service.enable_cache(mode_config.cache_size)
                    logger.info(f"✅ Embedding cache enabled: {mode_config.cache_size} entries")

                # Create hybrid service with mode-aware config (only enabled services)
                hybrid_service = HybridSimilarityService(
                    config,
                    tfidf_service=tfidf_service if mode_config.enable_tfidf else None,
                    semantic_service=semantic_service if mode_config.enable_embeddings else None,
                )

                # Check which semantic services are actually available
                stats = hybrid_service.get_statistics()
                services_available = stats.get('services_available', {})

                semantic_count = sum([
                    services_available.get('nlp', False),
                    services_available.get('synonyms', False),
                    services_available.get('tfidf', False),
                    services_available.get('embeddings', False)
                ])

                if semantic_count == 0:
                    logger.warning(
                        "⚠️ Hybrid similarity uitgeschakeld: geen semantische services beschikbaar. "
                        "Gebruik RapidFuzz-only. Installeer spacy/gensim/wn/sentence-transformers voor betere matches."
                    )
                    hybrid_service = None
                else:
                    active_methods = ", ".join(
                        k for k, v in services_available.items() if v and k != "rapidfuzz"
                    )
                    logger.info(
                        f"✅ Hybrid similarity actief met {semantic_count} semantische services: {active_methods}"
                    )
                    
                    # Log detailed mode configuration for debugging
                    logger.info(f"📊 Mode weights: RapidFuzz={mode_config.weight_rapidfuzz:.0%}, "
                               f"Lemma={mode_config.weight_lemmatized:.0%}, "
                               f"TF-IDF={mode_config.weight_tfidf:.0%}, "
                               f"Synonyms={mode_config.weight_synonyms:.0%}, "
                               f"Embeddings={mode_config.weight_embeddings:.0%}")
                    logger.info(f"📊 Mode enables: NLP={mode_config.enable_nlp}, "
                               f"TF-IDF={mode_config.enable_tfidf}, "
                               f"Synonyms={mode_config.enable_synonyms}, "
                               f"Embeddings={mode_config.enable_embeddings}")
                    
                    # IMPORTANT: Upgrade clustering to use hybrid similarity too!
                    clustering.similarity_service = hybrid_service
                    logger.info(f"🔗 Clustering upgraded to hybrid similarity mode: {mode.value.upper()}")
            except Exception as e:
                logger.warning(f"Could not initialize hybrid similarity: {e}")
                hybrid_service = None
        else:
            hybrid_service = None

        # Initialize custom instructions service (Step 0.5) if provided
        custom_instructions_service = None
        if extra_instruction:
            custom_instructions_service = CustomInstructionsService(
                fuzzy_service=base_similarity_service,
                semantic_service=semantic_service,
                hybrid_service=hybrid_service,
            )
            loaded_count = custom_instructions_service.load_instructions(extra_instruction)
            if loaded_count > 0:
                logger.info(f"✅ Custom instructions loaded: {loaded_count} regels")
            else:
                logger.warning("⚠️ Custom instructions provided but could not be parsed")
                custom_instructions_service = None

        analysis = AnalysisService(
            config,
            ai_analyzer=ai_analyzer,
            similarity_service=base_similarity_service,
            semantic_similarity_service=semantic_service,
            hybrid_similarity_service=hybrid_service,
            clause_library_service=None,
            admin_check_service=admin_check,
            custom_instructions_service=custom_instructions_service,
        )

        # Step 3: Load clause library if available
        if clause_library_files:
            _update_job(job, progress=21, message="📚 Clausulebibliotheek laden...")
            clause_library_service.load_from_files(clause_library_files)
            analysis.set_clause_library_service(clause_library_service)

        # Step 4: Convert to clauses
        _update_job(job, progress=23, message="📄 Data voorbereiden...")
        clauses = preprocessing.dataframe_to_clauses(
            df,
            text_col,
            policy_number_col=policy_number_col,
            source_file_name=policy_filename,
        )

        # Step 5: Clustering (multi-clause detection removed - now handled by length check)
        _update_job(job, progress=25, message="🔗 Slim clusteren...")
        log_section(logger, f"🔗 CLUSTERING ({len(clauses)} clauses)")

        # Progress callback for clustering (25% -> 50%)
        def clustering_progress(pct: int) -> None:
            actual_progress = 25 + int(pct * 0.25)  # Map 0-100 to 25-50
            _update_job(job, progress=actual_progress, message=f"🔗 Slim clusteren... ({pct}%)")

        with Timer(f"Cluster {len(clauses)} clauses"):
            clusters, clause_to_cluster = clustering.cluster_clauses(clauses, progress_callback=clustering_progress)

        logger.info(f"✅ Clustering complete: {len(clusters)} clusters from {len(clauses)} clauses")
        logger.info(f"   • Avg cluster size: {len(clauses) / len(clusters):.1f}")
        phase_timer.checkpoint(f"Clustering ({len(clusters)} clusters)")

        for clause in clauses:
            clause.cluster_id = clause_to_cluster.get(clause.id)

        _update_job(job, progress=50, message="🧠 Analyseren...")

        # Step 7: Analysis (simplified - no splitting)
        sections_to_use = policy_sections if use_conditions else []
        advice_map: Dict[str, Any] = {}

        total_clusters = len(clusters)
        for idx, cluster in enumerate(clusters):
            if idx % 10 == 0 and total_clusters:
                progress_pct = 50 + int((idx / total_clusters) * 40)
                _update_job(
                    job,
                    progress=progress_pct,
                    message=f"🧠 Analyseren... ({idx}/{total_clusters})",
                )

            advice = analysis.analyze_clusters(
                [cluster],
                sections_to_use,
                progress_callback=None,
            ).get(cluster.id)

            if not advice:
                from hienfeld.domain.analysis import (  # local import to avoid cycles
                    AdviceCode,
                    AnalysisAdvice,
                    ConfidenceLevel,
                )

                advice = AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason="Geen advies gegenereerd",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article="-",
                    category="UNKNOWN",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency,
                )

            advice_map[cluster.id] = advice

        # Step 8: Statistics
        _update_job(job, progress=95, message="📊 Resultaten samenstellen...")
        stats = export.get_statistics_summary(clauses, clusters, advice_map)
        stats["analysis_mode"] = (
            "with_conditions" if (use_conditions and policy_sections) else "internal_only"
        )
        stats["semantic_status"] = {
            "requested": use_semantic,
            "conditions_loaded": bool(policy_sections),
            "semantic_index_ready": getattr(analysis, "_semantic_index_ready", False),
            "hybrid_enabled": bool(hybrid_service),
            "tfidf_trained": tfidf_service.is_trained if tfidf_service else False,
            "rag_indexed": rag_service.is_ready() if rag_service else False,
        }

        # Step 9: Build results rows for API (simplified)
        result_rows: List[Dict[str, Any]] = []
        for cluster in clusters:
            advice = advice_map.get(cluster.id)
            text_content = (
                cluster.original_text[:500] + "..."
                if len(cluster.original_text) > 500
                else cluster.original_text
            )

            row = {
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "frequency": cluster.frequency,
                "advice_code": advice.advice_code if advice else "",
                "confidence": advice.confidence if advice else "",
                "reason": advice.reason if advice else "",
                "reference_article": advice.reference_article if advice else "",
                "original_text": text_content,
                "row_type": "SINGLE",  # Simple clustering (no PARENT/CHILD splitting)
                "parent_id": None,
            }
            result_rows.append(row)

        # Step 10: Generate Excel (one row per input row)
        results_df = export.build_results_dataframe(
            clauses,
            clusters,
            advice_map,
            include_original_columns=True,
            original_df=df,
        )
        excel_bytes = export.to_excel_bytes(
            results_df,
            include_summary=True,
            clusters=clusters,
            advice_map=advice_map,
        )

        job.stats = stats
        job.results = result_rows
        job.excel_bytes = excel_bytes
        job.excel_filename = "Hienfeld_Analyse.xlsx"

        _update_job(
            job,
            status=JobStatus.COMPLETED,
            progress=100,
            message="✅ Analyse voltooid!",
        )

        # Finish timing and log summary
        timing_stats = phase_timer.finish()
        logger.info("=" * 80)
        logger.info(f"🎉 Analysis job {job_id[:8]} COMPLETED")
        logger.info(f"   • Total clusters: {stats.get('unique_clusters', 0)}")
        logger.info(f"   • Input rows: {len(clauses)}")
        logger.info(f"   • Total time: {timing_stats['total_time']:.1f}s")
        logger.info("=" * 80)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analysis job %s failed: %s", job_id, exc)
        _update_job(
            job,
            status=JobStatus.FAILED,
            progress=0,
            message="❌ Analyse mislukt",
            error=str(exc),
        )


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

    job_id = str(uuid.uuid4())
    job = AnalysisJob(id=job_id)
    JOBS[job_id] = job

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
    job = JOBS.get(job_id)
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
    job = JOBS.get(job_id)
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
    job = JOBS.get(job_id)
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


@app.get("/api/health")
async def healthcheck() -> Dict[str, str]:
    """Simple health endpoint for monitoring."""
    return {"status": "ok"}


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


