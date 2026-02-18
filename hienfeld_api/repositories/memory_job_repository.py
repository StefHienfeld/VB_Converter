"""
In-memory implementation of the job repository.

This implementation stores jobs in a dictionary. It's suitable for
development and single-instance deployments.

Note: Jobs are lost when the server restarts.
"""

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, List, Optional

from hienfeld_api.models import AnalysisJob
from .job_repository import JobRepository

logger = logging.getLogger(__name__)

# GDPR: jobs auto-deleted after 24 hours
JOB_TTL_HOURS = 24


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

    def cleanup_expired_jobs(self) -> int:
        """
        Delete jobs older than JOB_TTL_HOURS.

        GDPR compliance: Article 5(1)(e) - storage limitation.
        Called periodically (every 30 min) via background task in app.py.

        Returns:
            Number of jobs deleted.
        """
        now = datetime.now(timezone.utc)
        ttl = timedelta(hours=JOB_TTL_HOURS)

        with self._lock:
            expired_ids = []
            for job_id, job in self._jobs.items():
                created = job.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created) > ttl:
                    expired_ids.append(job_id)

            for job_id in expired_ids:
                del self._jobs[job_id]
                logger.info(
                    "GDPR cleanup: deleted expired job %s (>%dh old)",
                    job_id,
                    JOB_TTL_HOURS,
                )

            if expired_ids:
                logger.info(
                    "GDPR cleanup: removed %d expired jobs, %d remaining",
                    len(expired_ids),
                    len(self._jobs),
                )

        return len(expired_ids)

    @property
    def job_count(self) -> int:
        """Current number of stored jobs."""
        return self.count()

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
