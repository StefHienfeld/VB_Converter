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

import uuid
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from hienfeld.config import load_config
from hienfeld.settings import get_settings

# Import models from new MVC structure
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
from hienfeld.services.reference_analysis_service import ReferenceAnalysisService

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

# Load environment settings
settings = get_settings()

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

    This mirrors the logic in `HienfeldState.run_analysis`, but operates
    without Reflex state and writes progress into the in-memory job.
    """
    job = job_repository.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found when starting analysis")
        return

    # Initialize phase timer for tracking entire pipeline
    phase_timer = PhaseTimer(f"Analysis Job {job_id[:8]}")

    try:
        job.update( status=JobStatus.RUNNING, progress=0, message="Initialiseren...")

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
        job.update( progress=5, message="📄 Bestand inlezen...")
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
            job.update( progress=10, message="📚 Voorwaarden verwerken...")
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
            job.update( progress=10, message="📊 Modus: Interne analyse")
            logger.info("ℹ️  No conditions files - internal analysis mode")
            phase_timer.checkpoint("No conditions (internal mode)")

        # Initialize semantic stack (embeddings, RAG, TF-IDF) if requested and possible
        semantic_stack_active = False

        log_section(logger, "🧠 SEMANTIC SERVICES INITIALIZATION")

        # Initialize semantic services for clustering (independent of conditions)
        if use_semantic and config.semantic.enabled:
            # Train TF-IDF on voorwaarden (if available and we have conditions)
            if policy_sections and tfidf_service.is_available and config.semantic.enable_tfidf:
                job.update( progress=12, message="🔤 TF-IDF model trainen...")
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
                job.update( progress=14, message="🧠 Embeddings laden...")
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

                    job.update( progress=16, message="📊 Vector store initialiseren...")
                    vector_store = create_vector_store(
                        method=config.ai.vector_store_type or "faiss",
                        embedding_dim=getattr(embeddings_service, "embedding_dim", 384),
                    )
                    job.update( progress=18, message="🔍 RAG index bouwen...")
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
            ai_enabled = bool(settings.get("ai_enabled"))
            env_settings = get_settings()
            openai_key = env_settings.openai_api_key

            if ai_enabled and openai_key:
                try:
                    # Import OpenAI client
                    from openai import OpenAI
                    openai_client = OpenAI(api_key=openai_key)

                    ai_analyzer = LLMAnalysisService(
                        client=openai_client,
                        rag_service=rag_service,
                        model_name=env_settings.llm_model or "gpt-4o-mini",
                    )
                    logger.info(f"✅ AI analysis enabled with model: {env_settings.llm_model}")
                except ImportError:
                    logger.warning("⚠️ OpenAI package not installed. Run: pip install openai")
                    ai_analyzer = None
                except Exception as exc:
                    logger.warning("LLM analyzer niet geactiveerd: %s", exc)
                    ai_analyzer = None
            elif ai_enabled and not openai_key:
                logger.warning("⚠️ AI enabled but OPENAI_API_KEY not set in .env")

            semantic_stack_active = bool(semantic_service or rag_service or tfidf_service.is_trained)
        else:
            if not use_semantic:
                logger.info("Semantische analyse uitgeschakeld via verzoek")
            elif not policy_sections:
                logger.info("Geen voorwaarden geladen: semantische stap wordt overgeslagen")

        # Initialize hybrid similarity service (v3.0 semantic enhancement)
        if HYBRID_AVAILABLE and config.semantic.enabled and use_semantic:
            job.update( progress=20, message="⚡ Hybrid similarity configureren...")
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

        # Initialize reference analysis service (for yearly vs monthly comparison)
        reference_service = None
        if reference_file:
            job.update(progress=22, message="📊 Referentie analyse laden...")
            ref_bytes, ref_filename = reference_file
            logger.info(f"📊 Loading reference file: {ref_filename} ({len(ref_bytes)} bytes)")

            try:
                reference_service = ReferenceAnalysisService(
                    config=config,
                    similarity_service=hybrid_service or base_similarity_service,
                )
                ref_count = reference_service.load_reference_file(ref_bytes, ref_filename)
                logger.info(f"✅ Reference analysis loaded: {ref_count} clausules uit {ref_filename}")
                phase_timer.checkpoint(f"Reference loaded ({ref_count} clauses)")
            except Exception as e:
                logger.warning(f"⚠️ Could not load reference file: {e}")
                reference_service = None

        analysis = AnalysisService(
            config,
            ai_analyzer=ai_analyzer,
            similarity_service=base_similarity_service,
            semantic_similarity_service=semantic_service,
            hybrid_similarity_service=hybrid_service,
            clause_library_service=None,
            admin_check_service=admin_check,
            custom_instructions_service=custom_instructions_service,
            reference_service=reference_service,
        )

        # Step 3: Load clause library if available
        if clause_library_files:
            job.update( progress=21, message="📚 Clausulebibliotheek laden...")
            clause_library_service.load_from_files(clause_library_files)
            analysis.set_clause_library_service(clause_library_service)

        # Step 4: Convert to clauses
        job.update( progress=23, message="📄 Data voorbereiden...")
        clauses = preprocessing.dataframe_to_clauses(
            df,
            text_col,
            policy_number_col=policy_number_col,
            source_file_name=policy_filename,
        )

        # Step 5: Clustering (multi-clause detection removed - now handled by length check)
        job.update( progress=25, message="🔗 Slim clusteren...")
        log_section(logger, f"🔗 CLUSTERING ({len(clauses)} clauses)")

        # Progress callback for clustering (25% -> 50%)
        def clustering_progress(pct: int) -> None:
            actual_progress = 25 + int(pct * 0.25)  # Map 0-100 to 25-50
            job.update( progress=actual_progress, message=f"🔗 Slim clusteren... ({pct}%)")

        with Timer(f"Cluster {len(clauses)} clauses"):
            clusters, clause_to_cluster = clustering.cluster_clauses(clauses, progress_callback=clustering_progress)

        logger.info(f"✅ Clustering complete: {len(clusters)} clusters from {len(clauses)} clauses")
        logger.info(f"   • Avg cluster size: {len(clauses) / len(clusters):.1f}")
        phase_timer.checkpoint(f"Clustering ({len(clusters)} clusters)")

        for clause in clauses:
            clause.cluster_id = clause_to_cluster.get(clause.id)

        job.update( progress=50, message="🧠 Analyseren...")

        # Step 7: Analysis (simplified - no splitting)
        sections_to_use = policy_sections if use_conditions else []

        # Progress callback for analysis (50% -> 90%)
        def analysis_progress(pct: int) -> None:
            actual_progress = 50 + int(pct * 0.40)  # Map 0-100 to 50-90
            job.update( progress=actual_progress, message=f"🧠 Analyseren... ({pct}%)")

        # FIXED: Analyze ALL clusters in a single call (was: per-cluster loop causing 989x re-initialization)
        with Timer(f"Analyze {len(clusters)} clusters"):
            advice_map = analysis.analyze_clusters(
                clusters,
                sections_to_use,
                progress_callback=analysis_progress,
            )

        phase_timer.checkpoint(f"Analysis ({len(clusters)} clusters)")

        # Validate all clusters have advice
        from hienfeld.domain.analysis import (  # local import to avoid cycles
            AdviceCode,
            AnalysisAdvice,
            ConfidenceLevel,
        )

        for cluster in clusters:
            if cluster.id not in advice_map:
                logger.warning(f"No advice generated for cluster {cluster.id}, creating fallback")
                advice_map[cluster.id] = AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason="Geen advies gegenereerd",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article="-",
                    category="UNKNOWN",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency,
                )

        # Step 8: Statistics
        job.update( progress=95, message="📊 Resultaten samenstellen...")
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
        # Build reference matches dict for export (if reference service is active)
        reference_matches = None
        gone_texts = None
        if reference_service:
            reference_matches = {}
            for cluster in clusters:
                # Use simplified text from leader for matching
                leader_text = cluster.leader.simplified_text if cluster.leader else cluster.leader_text
                ref_match = reference_service.find_match(leader_text)
                if ref_match:
                    reference_matches[cluster.id] = ref_match

            # Get texts from reference that weren't matched (disappeared from current data)
            gone_texts = reference_service.get_gone_texts()
            logger.info(f"📊 Reference comparison: {len(reference_matches)} matches, {len(gone_texts)} gone texts")

        results_df = export.build_results_dataframe(
            clauses,
            clusters,
            advice_map,
            include_original_columns=True,
            original_df=df,
            reference_matches=reference_matches,
        )
        excel_bytes = export.to_excel_bytes(
            results_df,
            include_summary=True,
            clusters=clusters,
            advice_map=advice_map,
            gone_texts=gone_texts,
        )

        job.stats = stats
        job.results = result_rows
        job.excel_bytes = excel_bytes
        job.excel_filename = "Hienfeld_Analyse.xlsx"

        job.update(
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
        job.update(
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


@app.get("/api/health")
async def healthcheck() -> Dict[str, str]:
    """Simple health endpoint for monitoring."""
    return {"status": "ok"}


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


