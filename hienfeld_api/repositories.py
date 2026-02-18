# hienfeld_api/repositories.py
"""
In-memory repository for job storage.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from hienfeld_api.models import AnalysisJob

logger = logging.getLogger(__name__)

# GDPR: jobs auto-deleted after 24 hours (Article 5(1)(e) storage limitation)
JOB_TTL_HOURS = 24


class MemoryJobRepository:
    """Simple in-memory job storage with GDPR-compliant TTL cleanup."""

    def __init__(self):
        self._jobs: Dict[str, AnalysisJob] = {}

    def save(self, job: AnalysisJob) -> None:
        """Save or update a job"""
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """Get a job by ID"""
        return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Delete a job"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def list_all(self) -> List[AnalysisJob]:
        """List all jobs"""
        return list(self._jobs.values())

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

        expired_ids = []
        for job_id, job in self._jobs.items():
            # created_at may be naive (no tzinfo) — handle both cases
            created = job.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created) > ttl:
                expired_ids.append(job_id)

        for job_id in expired_ids:
            del self._jobs[job_id]
            logger.info("GDPR cleanup: deleted expired job %s (>%dh old)", job_id, JOB_TTL_HOURS)

        if expired_ids:
            logger.info("GDPR cleanup: removed %d expired jobs, %d remaining", len(expired_ids), len(self._jobs))

        return len(expired_ids)

    @property
    def job_count(self) -> int:
        """Current number of stored jobs."""
        return len(self._jobs)
