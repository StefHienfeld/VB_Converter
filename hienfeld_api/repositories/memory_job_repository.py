"""
In-memory implementation of the job repository.

This implementation stores jobs in a dictionary. It's suitable for
development and single-instance deployments.

Note: Jobs are lost when the server restarts.
"""

from threading import Lock
from typing import Dict, List, Optional

from hienfeld_api.models import AnalysisJob
from .job_repository import JobRepository


class MemoryJobRepository(JobRepository):
    """
    Thread-safe in-memory job storage.

    Uses a dictionary with a lock for thread safety during
    concurrent access from background tasks.
    """

    def __init__(self) -> None:
        """Initialize empty job storage."""
        self._jobs: Dict[str, AnalysisJob] = {}
        self._lock = Lock()

    def save(self, job: AnalysisJob) -> None:
        """Store or update a job."""
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """Retrieve a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Delete a job."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    def list_all(self) -> List[AnalysisJob]:
        """List all jobs."""
        with self._lock:
            return list(self._jobs.values())

    def count(self) -> int:
        """Count total jobs."""
        with self._lock:
            return len(self._jobs)

    def clear(self) -> int:
        """
        Clear all jobs (for testing).

        Returns:
            Number of jobs cleared
        """
        with self._lock:
            count = len(self._jobs)
            self._jobs.clear()
            return count
