"""
Job model for analysis jobs.

Contains the AnalysisJob dataclass and JobStatus enum for tracking
background analysis jobs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    """Status states for an analysis job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AnalysisJob:
    """
    Represents a background analysis job.

    Tracks the state, progress, and results of an analysis pipeline run.
    """
    id: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    status_message: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Results (populated when job completes)
    stats: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None
    excel_bytes: Optional[bytes] = None
    excel_filename: Optional[str] = None

    def update(
        self,
        *,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update job state safely.

        Args:
            status: New job status
            progress: Progress percentage (0-100)
            message: Status message for UI
            error: Error message if failed
        """
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = int(progress)
        if message is not None:
            self.status_message = message
        if error is not None:
            self.error = error

    @property
    def is_complete(self) -> bool:
        """Check if job has completed (success or failure)."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED)

    @property
    def is_running(self) -> bool:
        """Check if job is currently running."""
        return self.status == JobStatus.RUNNING

    @property
    def has_results(self) -> bool:
        """Check if job has results available."""
        return self.status == JobStatus.COMPLETED and self.results is not None
