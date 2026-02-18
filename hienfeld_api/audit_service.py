"""
GDPR Audit logging service for VB Converter.

Records metadata about every analysis action (start, completion, failure)
for compliance purposes. Never stores personal data or document content —
only technical metadata (job ID, filenames, duration, status).

Audit log table: audit_logs (see models/db_models.py)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


class AuditService:
    """
    Records GDPR-compliant audit log entries.

    Falls back to logger-only mode when no database session factory
    is available (e.g. pure in-memory mode).
    """

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory

    def log_analysis_started(
        self,
        job_id: str,
        user_id: str,
        file_names: List[str],
        analysis_mode: str,
    ) -> None:
        """Log the start of an analysis job."""
        self._write(
            job_id=job_id,
            user_id=user_id,
            action="analysis_started",
            outcome="pending",
            file_names=file_names,
            analysis_mode=analysis_mode,
            duration_seconds=None,
        )

    def log_analysis_completed(
        self,
        job_id: str,
        user_id: str,
        duration_seconds: int,
        analysis_mode: Optional[str] = None,
    ) -> None:
        """Log successful completion of an analysis job."""
        self._write(
            job_id=job_id,
            user_id=user_id,
            action="analysis_completed",
            outcome="completed",
            file_names=None,
            analysis_mode=analysis_mode,
            duration_seconds=duration_seconds,
        )

    def log_analysis_failed(
        self,
        job_id: str,
        user_id: str,
        duration_seconds: int,
        analysis_mode: Optional[str] = None,
    ) -> None:
        """Log a failed analysis job."""
        self._write(
            job_id=job_id,
            user_id=user_id,
            action="analysis_failed",
            outcome="failed",
            file_names=None,
            analysis_mode=analysis_mode,
            duration_seconds=duration_seconds,
        )

    def log_job_deleted(self, job_id: str, user_id: str) -> None:
        """Log deletion of a job (GDPR erasure)."""
        self._write(
            job_id=job_id,
            user_id=user_id,
            action="job_deleted",
            outcome=None,
            file_names=None,
            analysis_mode=None,
            duration_seconds=None,
        )

    def _write(
        self,
        job_id: str,
        user_id: str,
        action: str,
        outcome: Optional[str],
        file_names: Optional[List[str]],
        analysis_mode: Optional[str],
        duration_seconds: Optional[int],
    ) -> None:
        file_names_str = ", ".join(file_names) if file_names else None

        # Always log to application log (visible even without DB)
        logger.info(
            "AUDIT | action=%s job_id=%s user=%s outcome=%s mode=%s duration=%s files=[%s]",
            action,
            job_id,
            user_id,
            outcome or "-",
            analysis_mode or "-",
            f"{duration_seconds}s" if duration_seconds is not None else "-",
            file_names_str or "",
        )

        if not self._session_factory:
            return

        try:
            from hienfeld_api.models.db_models import AuditLog

            session = self._session_factory()
            try:
                entry = AuditLog(
                    timestamp=datetime.now(timezone.utc),
                    job_id=job_id,
                    user_id=user_id,
                    action=action,
                    outcome=outcome,
                    file_names=file_names_str,
                    analysis_mode=analysis_mode,
                    duration_seconds=duration_seconds,
                )
                session.add(entry)
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            # Never let audit logging fail the main request
            logger.error("Audit log write failed (non-fatal): %s", exc)
