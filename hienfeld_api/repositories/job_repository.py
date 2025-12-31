"""
Abstract repository interface for job storage.

This interface defines the contract for job persistence, allowing
different implementations (in-memory, database, Redis, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from hienfeld_api.models import AnalysisJob


class JobRepository(ABC):
    """
    Abstract interface for job storage.

    Implementations must provide thread-safe storage and retrieval
    of AnalysisJob objects.
    """

    @abstractmethod
    def save(self, job: AnalysisJob) -> None:
        """
        Store or update a job.

        Args:
            job: The job to store
        """
        pass

    @abstractmethod
    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """
        Retrieve a job by ID.

        Args:
            job_id: The job's unique identifier

        Returns:
            The job if found, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: The job's unique identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_all(self) -> List[AnalysisJob]:
        """
        List all jobs.

        Returns:
            List of all stored jobs
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Count total jobs.

        Returns:
            Number of stored jobs
        """
        pass
