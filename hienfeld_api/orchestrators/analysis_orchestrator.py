"""
Analysis orchestrator for coordinating the analysis pipeline.

This orchestrator manages the complete analysis workflow, delegating
to specialized services for each step of the pipeline.

The pipeline consists of 8 clear phases:
1. Load and configure
2. Ingest policy file
3. Parse conditions
4. Initialize semantic stack
5. Preprocess data
6. Run clustering
7. Run analysis
8. Generate results
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from hienfeld_api.models import AnalysisJob, JobStatus
from hienfeld_api.factories import ServiceFactory, ServiceContainer
from hienfeld_api.repositories import JobRepository
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.domain.clause import Clause
from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.logging_config import get_logger, log_section
from hienfeld.utils.timing import PhaseTimer, Timer

logger = get_logger("orchestrator")

# Feature flag for gradual migration
USE_NEW_ORCHESTRATOR = os.getenv("USE_NEW_ORCHESTRATOR", "true").lower() == "true"


@dataclass
class AnalysisInput:
    """
    Input data for an analysis job.

    Encapsulates all the data needed to run an analysis,
    making it easy to pass around and test.
    """
    policy_bytes: bytes
    policy_filename: str
    conditions_files: List[Tuple[bytes, str]]
    clause_library_files: List[Tuple[bytes, str]]
    reference_file: Optional[Tuple[bytes, str]]
    settings: Dict[str, Any]

    @property
    def has_conditions(self) -> bool:
        """Check if conditions files were provided."""
        return bool(self.conditions_files)

    @property
    def has_clause_library(self) -> bool:
        """Check if clause library files were provided."""
        return bool(self.clause_library_files)

    @property
    def has_reference(self) -> bool:
        """Check if reference file was provided."""
        return self.reference_file is not None

    @property
    def extra_instruction(self) -> str:
        """Get the extra instruction text."""
        return str(self.settings.get("extra_instruction", "")).strip()

    @property
    def use_conditions(self) -> bool:
        """Check if conditions should be used."""
        return bool(self.settings.get("use_conditions", True))

    @property
    def use_semantic(self) -> bool:
        """Check if semantic analysis should be used."""
        return bool(self.settings.get("use_semantic", True))

    @property
    def ai_enabled(self) -> bool:
        """Check if AI analysis should be enabled."""
        return bool(self.settings.get("ai_enabled", False))


class AnalysisOrchestrator:
    """
    Orchestrates the complete analysis pipeline.

    This class coordinates all the services needed to run an analysis,
    managing the flow from file ingestion through to results export.

    The pipeline consists of these main phases:
    1. Configuration and service initialization
    2. File loading (policy, conditions, clause library)
    3. Preprocessing and clustering
    4. Analysis (5-step waterfall)
    5. Results generation and export
    """

    def __init__(
        self,
        service_factory: Optional[ServiceFactory] = None,
        job_repository: Optional[JobRepository] = None
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            service_factory: Factory for creating services. If None, creates one.
            job_repository: Repository for job storage (optional, for legacy support)
        """
        self._factory = service_factory or ServiceFactory()
        self._job_repository = job_repository

    def run(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        """
        Execute the complete analysis pipeline.

        Updates the job object with progress, results, and errors.
        This method is designed to be called as a background task.

        Args:
            job: The job to update with progress and results
            input_data: All input data for the analysis
            progress_callback: Optional callback for progress updates

        Note:
            This method catches all exceptions and updates the job
            status accordingly. It never raises exceptions.
        """
        try:
            self._execute_pipeline(job, input_data, progress_callback)
        except Exception as exc:
            logger.exception("Analysis job %s failed: %s", job.id, exc)
            job.update(
                status=JobStatus.FAILED,
                progress=0,
                message="Analyse mislukt",
                error=str(exc),
            )

    def _execute_pipeline(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        progress_callback: Optional[Callable[[int, str], None]],
    ) -> None:
        """
        Internal pipeline execution.

        This method contains the actual pipeline logic and may raise exceptions.
        The public run() method wraps this with error handling.
        """
        phase_timer = PhaseTimer(f"Analysis Job {job.id[:8]}")

        job.update(status=JobStatus.RUNNING, progress=0, message="Initialiseren...")
        log_section(logger, f"NEW ANALYSIS JOB: {job.id}")

        # Phase 1: Load and configure
        container = self._phase1_load_and_configure(job, input_data, phase_timer)

        # Phase 2: Ingest policy file
        df, text_col, policy_number_col = self._phase2_ingest_policy(
            job, input_data, container, phase_timer
        )

        # Phase 3: Parse conditions
        policy_sections = self._phase3_parse_conditions(
            job, input_data, container, phase_timer
        )

        # Phase 4: Initialize semantic stack
        self._phase4_initialize_semantic_stack(
            job, input_data, container, policy_sections, phase_timer
        )

        # Phase 5: Preprocess data
        clauses = self._phase5_preprocess_data(
            job, input_data, container, df, text_col, policy_number_col, phase_timer
        )

        # Phase 6: Run clustering
        clusters, clause_to_cluster = self._phase6_run_clustering(
            job, container, clauses, phase_timer
        )

        # Update clause->cluster mapping
        for clause in clauses:
            clause.cluster_id = clause_to_cluster.get(clause.id)

        # Phase 7: Run analysis
        advice_map = self._phase7_run_analysis(
            job, container, clusters, policy_sections, input_data.use_conditions, phase_timer
        )

        # Phase 8: Generate results
        self._phase8_generate_results(
            job, input_data, container, df, clauses, clusters, advice_map,
            policy_sections, phase_timer
        )

        # Complete
        timing_stats = phase_timer.finish()
        logger.info("=" * 80)
        logger.info(f"Analysis job {job.id[:8]} COMPLETED")
        logger.info(f"   Total clusters: {job.stats.get('unique_clusters', 0) if job.stats else 0}")
        logger.info(f"   Input rows: {len(clauses)}")
        logger.info(f"   Total time: {timing_stats['total_time']:.1f}s")
        logger.info("=" * 80)

    def _phase1_load_and_configure(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        phase_timer: PhaseTimer
    ) -> ServiceContainer:
        """Phase 1: Load configuration and create base services."""
        job.update(progress=2, message="Configuratie laden...")

        config = self._factory.create_config(input_data.settings)
        container = self._factory.create_base_services(config)

        mode_config = config.semantic.get_active_config()
        logger.info(f"Analysis mode: {input_data.settings.get('analysis_mode', 'balanced').upper()}")
        logger.info(f"   Time multiplier: {mode_config.time_multiplier}x")
        logger.info(f"   Cluster threshold: {input_data.settings.get('cluster_accuracy', 90)}%")
        logger.info(f"   Min frequency: {input_data.settings.get('min_frequency', 20)}")
        logger.info(f"   Window size: {input_data.settings.get('window_size', 100)}")

        phase_timer.checkpoint("Configuration loaded")
        return container

    def _phase2_ingest_policy(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        container: ServiceContainer,
        phase_timer: PhaseTimer
    ) -> Tuple[Any, str, Optional[str]]:
        """Phase 2: Load and parse the policy file."""
        job.update(progress=5, message="Bestand inlezen...")
        logger.info(f"Loading policy file: {input_data.policy_filename} ({len(input_data.policy_bytes)} bytes)")

        with Timer("Load policy file"):
            df = container.ingestion.load_policy_file(
                input_data.policy_bytes,
                input_data.policy_filename
            )
            text_col = container.ingestion.detect_text_column(df)
            policy_number_col = container.ingestion.detect_policy_number_column(df)

        logger.info(f"Policy loaded: {len(df)} rows, text column: '{text_col}'")
        phase_timer.checkpoint(f"Policy file loaded ({len(df)} rows)")

        return df, text_col, policy_number_col

    def _phase3_parse_conditions(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        container: ServiceContainer,
        phase_timer: PhaseTimer
    ) -> List[PolicyDocumentSection]:
        """Phase 3: Parse conditions files."""
        policy_sections: List[PolicyDocumentSection] = []

        if input_data.use_conditions and input_data.conditions_files:
            job.update(progress=10, message="Voorwaarden verwerken...")
            logger.info(f"Parsing {len(input_data.conditions_files)} conditions files...")

            with Timer(f"Parse {len(input_data.conditions_files)} conditions files"):
                for file_bytes, filename in input_data.conditions_files:
                    try:
                        logger.debug(f"   Parsing {filename} ({len(file_bytes)} bytes)...")
                        sections = container.policy_parser.parse_policy_file(file_bytes, filename)
                        policy_sections.extend(sections)
                        logger.debug(f"     -> {len(sections)} sections extracted")
                    except Exception as exc:
                        logger.warning(f"Failed to parse {filename}: {exc}")

            logger.info(f"Conditions parsed: {len(policy_sections)} total sections")
            phase_timer.checkpoint(f"Conditions parsed ({len(policy_sections)} sections)")
        else:
            job.update(progress=10, message="Modus: Interne analyse")
            logger.info("No conditions files - internal analysis mode")
            phase_timer.checkpoint("No conditions (internal mode)")

        return policy_sections

    def _phase4_initialize_semantic_stack(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        container: ServiceContainer,
        policy_sections: List[PolicyDocumentSection],
        phase_timer: PhaseTimer
    ) -> None:
        """Phase 4: Initialize semantic services (TF-IDF, embeddings, RAG, hybrid)."""
        log_section(logger, "SEMANTIC SERVICES INITIALIZATION")

        if input_data.use_semantic and container.config.semantic.enabled:
            job.update(progress=12, message="Semantische services laden...")

            self._factory.initialize_semantic_stack(
                container,
                policy_sections,
                use_semantic=input_data.use_semantic,
                ai_enabled=input_data.ai_enabled
            )

            phase_timer.checkpoint("Semantic stack initialized")

            # Initialize custom instructions (Step 0.5)
            if input_data.extra_instruction:
                self._factory.create_custom_instructions(
                    container,
                    input_data.extra_instruction
                )

            # Initialize reference service
            if input_data.reference_file:
                job.update(progress=18, message="Referentie analyse laden...")
                self._factory.create_reference_service(container, input_data.reference_file)
                phase_timer.checkpoint("Reference service initialized")
        else:
            logger.info("Semantic analysis disabled")

        # Load clause library
        if input_data.clause_library_files:
            job.update(progress=20, message="Clausulebibliotheek laden...")
            container.clause_library.load_from_files(input_data.clause_library_files)
            logger.info(f"Clause library loaded: {container.clause_library.clause_count} clauses")

        # Create analysis service with all dependencies
        self._factory.create_analysis_service(container)

        # Connect clause library to analysis service
        if container.clause_library.is_loaded and container.analysis:
            container.analysis.set_clause_library_service(container.clause_library)

    def _phase5_preprocess_data(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        container: ServiceContainer,
        df: Any,
        text_col: str,
        policy_number_col: Optional[str],
        phase_timer: PhaseTimer
    ) -> List[Clause]:
        """Phase 5: Convert DataFrame to Clause objects."""
        job.update(progress=23, message="Data voorbereiden...")

        clauses = container.preprocessing.dataframe_to_clauses(
            df,
            text_col,
            policy_number_col=policy_number_col,
            source_file_name=input_data.policy_filename,
        )

        phase_timer.checkpoint(f"Data preprocessed ({len(clauses)} clauses)")
        return clauses

    def _phase6_run_clustering(
        self,
        job: AnalysisJob,
        container: ServiceContainer,
        clauses: List[Clause],
        phase_timer: PhaseTimer
    ) -> Tuple[List[Cluster], Dict[str, str]]:
        """Phase 6: Cluster similar clauses."""
        job.update(progress=25, message="Slim clusteren...")
        log_section(logger, f"CLUSTERING ({len(clauses)} clauses)")

        # Progress callback for clustering (25% -> 50%)
        def clustering_progress(pct: int) -> None:
            actual_progress = 25 + int(pct * 0.25)
            job.update(progress=actual_progress, message=f"Slim clusteren... ({pct}%)")

        with Timer(f"Cluster {len(clauses)} clauses"):
            clusters, clause_to_cluster = container.clustering.cluster_clauses(
                clauses,
                progress_callback=clustering_progress
            )

        logger.info(f"Clustering complete: {len(clusters)} clusters from {len(clauses)} clauses")
        logger.info(f"   Avg cluster size: {len(clauses) / len(clusters):.1f}")
        phase_timer.checkpoint(f"Clustering ({len(clusters)} clusters)")

        return clusters, clause_to_cluster

    def _phase7_run_analysis(
        self,
        job: AnalysisJob,
        container: ServiceContainer,
        clusters: List[Cluster],
        policy_sections: List[PolicyDocumentSection],
        use_conditions: bool,
        phase_timer: PhaseTimer
    ) -> Dict[str, AnalysisAdvice]:
        """Phase 7: Analyze clusters with 5-step waterfall pipeline."""
        job.update(progress=50, message="Analyseren...")

        sections_to_use = policy_sections if use_conditions else []

        # Progress callback for analysis (50% -> 90%)
        def analysis_progress(pct: int) -> None:
            actual_progress = 50 + int(pct * 0.40)
            job.update(progress=actual_progress, message=f"Analyseren... ({pct}%)")

        with Timer(f"Analyze {len(clusters)} clusters"):
            advice_map = container.analysis.analyze_clusters(
                clusters,
                sections_to_use,
                progress_callback=analysis_progress,
            )

        phase_timer.checkpoint(f"Analysis ({len(clusters)} clusters)")

        # Validate all clusters have advice
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

        return advice_map

    def _phase8_generate_results(
        self,
        job: AnalysisJob,
        input_data: AnalysisInput,
        container: ServiceContainer,
        df: Any,
        clauses: List[Clause],
        clusters: List[Cluster],
        advice_map: Dict[str, AnalysisAdvice],
        policy_sections: List[PolicyDocumentSection],
        phase_timer: PhaseTimer
    ) -> None:
        """Phase 8: Generate statistics, results, and Excel report."""
        job.update(progress=95, message="Resultaten samenstellen...")

        # Statistics
        stats = container.export.get_statistics_summary(clauses, clusters, advice_map)
        stats["analysis_mode"] = (
            "with_conditions" if (input_data.use_conditions and policy_sections) else "internal_only"
        )
        stats["semantic_status"] = {
            "requested": input_data.use_semantic,
            "conditions_loaded": bool(policy_sections),
            "semantic_index_ready": getattr(container.analysis, "_semantic_index_ready", False),
            "hybrid_enabled": container.hybrid is not None,
            "tfidf_trained": container.tfidf.is_trained if container.tfidf else False,
            "rag_indexed": container.rag.is_ready() if container.rag else False,
        }

        # Build results rows for API
        result_rows: List[Dict[str, Any]] = []
        for cluster in clusters:
            advice = advice_map.get(cluster.id)
            text_content = (
                cluster.original_text[:500] + "..."
                if len(cluster.original_text) > 500
                else cluster.original_text
            )

            # Determine action_status from reference match (if available)
            action_status = None
            if container.reference and container.reference.is_loaded:
                # Get reference match for cluster leader text
                leader_text = cluster.leader_clause.simplified_text if cluster.leader_clause else ""
                ref_match = container.reference.find_match(leader_text)
                if ref_match is None:
                    action_status = "🆕 Nieuw"
                else:
                    ref_status = (ref_match.reference_clause.status or "").strip().lower()
                    done_indicators = ['ja', 'yes', 'gedaan', 'done', 'x', '✓', '✅', 'afgerond', 'klaar']
                    if any(indicator in ref_status for indicator in done_indicators):
                        action_status = "✅ Afgerond"
                    else:
                        action_status = "🔲 Open"

            row = {
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "frequency": cluster.frequency,
                "advice_code": advice.advice_code if advice else "",
                "confidence": advice.confidence if advice else "",
                "reason": advice.reason if advice else "",
                "reference_article": advice.reference_article if advice else "",
                "original_text": text_content,
                "row_type": "SINGLE",
                "parent_id": None,
                "action_status": action_status,
            }
            result_rows.append(row)

        # Generate Excel report
        gone_texts = None
        if container.reference:
            job.update(progress=96, message="Excel genereren met referentie vergelijking...")
            ref_count = len(container.reference._reference_data.clauses) if container.reference._reference_data else 0
            logger.info(f"Reference service active: {ref_count} reference clauses loaded")

        results_df = container.export.build_results_dataframe(
            clauses,
            clusters,
            advice_map,
            include_original_columns=True,
            original_df=df,
            reference_service=container.reference,
        )

        # Get gone texts after export
        if container.reference:
            gone_texts = container.reference.get_gone_texts()
            stats_ref = container.reference.get_statistics()
            logger.info(f"Reference comparison: {stats_ref.get('matched', 0)} matches, {len(gone_texts)} gone texts")

        excel_bytes = container.export.to_excel_bytes(
            results_df,
            include_summary=True,
            clusters=clusters,
            advice_map=advice_map,
            gone_texts=gone_texts,
        )

        phase_timer.checkpoint("Results generated")

        # Update job with final results
        job.stats = stats
        job.results = result_rows
        job.excel_bytes = excel_bytes
        job.excel_filename = "Hienfeld_Analyse.xlsx"

        job.update(
            status=JobStatus.COMPLETED,
            progress=100,
            message="Analyse voltooid!",
        )

    def create_progress_updater(
        self,
        job: AnalysisJob,
        start_pct: int,
        end_pct: int,
    ) -> Callable[[int], None]:
        """
        Create a progress callback that maps 0-100 to a specific range.

        Args:
            job: The job to update
            start_pct: Starting percentage (e.g., 25)
            end_pct: Ending percentage (e.g., 50)

        Returns:
            A callback function that updates job progress
        """
        range_size = end_pct - start_pct

        def callback(pct: int) -> None:
            actual = start_pct + int(pct * range_size / 100)
            job.update(progress=actual)

        return callback
