"""
Analysis orchestrator for coordinating the analysis pipeline.

This orchestrator manages the complete analysis workflow, delegating
to specialized services for each step of the pipeline.

Note: This is a wrapper that will eventually replace _run_analysis_job
in app.py. For now, it provides the structure while the actual
implementation remains in app.py for stability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from hienfeld_api.models import AnalysisJob, JobStatus
from hienfeld_api.factories import ServiceFactory
from hienfeld.logging_config import get_logger

logger = get_logger("orchestrator")


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
    def extra_instruction(self) -> str:
        """Get the extra instruction text."""
        return str(self.settings.get("extra_instruction", "")).strip()


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

    def __init__(self, service_factory: Optional[ServiceFactory] = None) -> None:
        """
        Initialize the orchestrator.

        Args:
            service_factory: Factory for creating services. If None, creates one.
        """
        self._factory = service_factory or ServiceFactory()

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
        # For now, this is a placeholder. The actual implementation
        # remains in app.py._run_analysis_job for stability.
        #
        # Future refactoring will move the logic here step by step:
        # 1. _load_and_configure() - Load config and create services
        # 2. _ingest_files() - Load policy and conditions
        # 3. _initialize_semantic_stack() - Setup embeddings, RAG, etc.
        # 4. _run_clustering() - Cluster the clauses
        # 5. _run_analysis() - Execute 5-step waterfall
        # 6. _generate_results() - Build results and Excel
        raise NotImplementedError(
            "Pipeline execution is currently handled by _run_analysis_job in app.py. "
            "This orchestrator will be fully implemented in a future refactoring phase."
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
