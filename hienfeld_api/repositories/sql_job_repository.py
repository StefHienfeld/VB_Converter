"""
SQLAlchemy implementation of the job repository.

Stores jobs in PostgreSQL (or SQLite for dev/test). Survives server restarts.
GDPR-compliant: includes cleanup_expired_jobs() for TTL enforcement.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from hienfeld_api.models import AnalysisJob
from hienfeld_api.models.db_models import JobRecord
from hienfeld_api.models.job import JobStatus
from .job_repository import JobRepository

logger = logging.getLogger(__name__)

# GDPR: jobs auto-deleted after 24 hours (Article 5(1)(e) storage limitation)
JOB_TTL_HOURS = 24


class SQLJobRepository(JobRepository):
    """
    PostgreSQL-backed job repository using SQLAlchemy.

    Thread-safe: each operation opens/closes its own session.
    Results and Excel bytes are persisted, surviving server restarts.

    GDPR compliance:
    - cleanup_expired_jobs() removes jobs older than JOB_TTL_HOURS
    - Called automatically every 30 minutes via background task in app.py
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        """
        Initialize with a session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker bound to an engine
        """
        self._session_factory = session_factory

    def _get_session(self) -> Session:
        """Create a new session."""
        return self._session_factory()

    def save(self, job: AnalysisJob) -> None:
        """
        Upsert a job (insert or update).

        Handles both new jobs (INSERT) and progress updates (UPDATE).
        """
        session = self._get_session()
        try:
            existing = session.get(JobRecord, job.id)
            if existing:
                # Update existing record in-place
                existing.status = job.status.value if isinstance(job.status, JobStatus) else job.status
                existing.progress = job.progress
                existing.status_message = job.status_message or ""
                existing.error = job.error
                existing.excel_bytes = job.excel_bytes
                existing.excel_filename = job.excel_filename

                if job.stats is not None:
                    existing.stats_json = json.dumps(job.stats, ensure_ascii=False, default=str)
                if job.results is not None:
                    existing.results_json = json.dumps(job.results, ensure_ascii=False, default=str)
            else:
                record = JobRecord.from_domain(job)
                session.add(record)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """Retrieve a job by ID. Returns None if not found."""
        session = self._get_session()
        try:
            record = session.get(JobRecord, job_id)
            if record is None:
                return None
            return record.to_domain()
        finally:
            session.close()

    def delete(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted, False if not found."""
        session = self._get_session()
        try:
            record = session.get(JobRecord, job_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_all(self) -> List[AnalysisJob]:
        """List all jobs (ordered by creation time, newest first)."""
        session = self._get_session()
        try:
            stmt = select(JobRecord).order_by(JobRecord.created_at.desc())
            records = session.execute(stmt).scalars().all()
            return [r.to_domain() for r in records]
        finally:
            session.close()

    def count(self) -> int:
        """Return total number of stored jobs."""
        session = self._get_session()
        try:
            from sqlalchemy import func
            result = session.execute(
                select(func.count()).select_from(JobRecord)
            ).scalar()
            return result or 0
        finally:
            session.close()

    @property
    def job_count(self) -> int:
        """Current number of stored jobs (property alias for count())."""
        return self.count()

    def cleanup_expired_jobs(self) -> int:
        """
        Delete jobs older than JOB_TTL_HOURS.

        GDPR compliance: Article 5(1)(e) - storage limitation.
        Called periodically (every 30 min) via background task in app.py.

        Returns:
            Number of jobs deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=JOB_TTL_HOURS)
        session = self._get_session()
        try:
            # Use SQLAlchemy bulk delete for efficiency
            stmt = (
                delete(JobRecord)
                .where(JobRecord.created_at < cutoff)
                .returning(JobRecord.id)
            )
            result = session.execute(stmt)
            deleted_ids = [row[0] for row in result.fetchall()]
            session.commit()

            count = len(deleted_ids)
            if count:
                logger.info(
                    "GDPR cleanup: deleted %d expired jobs (>%dh old)",
                    count,
                    JOB_TTL_HOURS,
                )
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
