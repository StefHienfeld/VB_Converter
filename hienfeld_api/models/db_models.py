"""
SQLAlchemy ORM models for database persistence.

Defines the database schema for analysis jobs. These models map to
PostgreSQL (or SQLite for local dev) tables.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hienfeld_api.database import Base
from hienfeld_api.models.job import JobStatus


class JobRecord(Base):
    """
    Database representation of an AnalysisJob.

    Maps to the 'analysis_jobs' table. Stores all job state including
    results and Excel report bytes for persistence across server restarts.
    """

    __tablename__ = "analysis_jobs"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Job state
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JobStatus.PENDING.value,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Results (JSON-serialized, stored as TEXT)
    # Using Text instead of JSON for cross-database compatibility
    stats_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    results_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Excel report (binary, can be several MB)
    excel_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    excel_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def to_domain(self):
        """Convert database record to AnalysisJob domain object."""
        from hienfeld_api.models.job import AnalysisJob

        job = AnalysisJob(
            id=self.id,
            status=JobStatus(self.status),
            progress=self.progress,
            status_message=self.status_message or "",
            error=self.error,
            created_at=self.created_at,
            excel_bytes=self.excel_bytes,
            excel_filename=self.excel_filename,
        )

        if self.stats_json:
            try:
                job.stats = json.loads(self.stats_json)
            except (json.JSONDecodeError, ValueError):
                job.stats = None

        if self.results_json:
            try:
                job.results = json.loads(self.results_json)
            except (json.JSONDecodeError, ValueError):
                job.results = None

        return job

    @classmethod
    def from_domain(cls, job) -> "JobRecord":
        """Create database record from AnalysisJob domain object."""
        record = cls(
            id=job.id,
            status=job.status.value if isinstance(job.status, JobStatus) else job.status,
            progress=job.progress,
            status_message=job.status_message or "",
            error=job.error,
            created_at=job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=timezone.utc),
            excel_bytes=job.excel_bytes,
            excel_filename=job.excel_filename,
        )

        if job.stats is not None:
            record.stats_json = json.dumps(job.stats, ensure_ascii=False, default=str)

        if job.results is not None:
            record.results_json = json.dumps(job.results, ensure_ascii=False, default=str)

        return record


class AuditLog(Base):
    """
    GDPR audit log for analysis actions.

    Records every analysis start and completion for compliance.
    Never stores personal data — only metadata (job_id, filenames, status).
    Maps to the 'audit_logs' table.
    """

    __tablename__ = "audit_logs"

    # Primary key (auto-increment)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Timestamp of the event (UTC)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Which job does this event belong to
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # User identifier (anonymous "dev-user" in dev, username in prod)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, default="anonymous")

    # Action: "analysis_started" | "analysis_completed" | "analysis_failed" | "job_deleted"
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # Outcome / status at time of event ("pending", "completed", "failed", etc.)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Filenames of uploaded files (no content, no personal data — only metadata)
    # Stored as comma-separated list: "polisbestand.xlsx, voorwaarden.pdf"
    file_names: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analysis mode used: FAST / BALANCED / ACCURATE
    analysis_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Duration in seconds (None for started events, set on completed/failed)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
