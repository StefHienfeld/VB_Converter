# hienfeld_api/repositories.py
"""
In-memory repository for job storage.
"""
from typing import Dict, Optional
from hienfeld_api.models import AnalysisJob


class MemoryJobRepository:
    """Simple in-memory job storage"""

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

    def list_all(self) -> list:
        """List all jobs"""
        return list(self._jobs.values())
