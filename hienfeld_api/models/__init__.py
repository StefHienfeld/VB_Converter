"""
Models package for Hienfeld VB Converter API.

Contains:
- job.py: AnalysisJob dataclass and JobStatus enum
- requests.py: Pydantic request/response models
- db_models.py: SQLAlchemy ORM models (jobs, audit)
- library_models.py: SQLAlchemy ORM models (product libraries)
"""

from .job import AnalysisJob, JobStatus
from .requests import (
    StartAnalysisResponse,
    JobStatusResponse,
    AnalysisResultRowModel,
    AnalysisResultsResponse,
    UploadPreviewResponse,
    FileUploadLimits,
    UploadValidationError,
    AnalysisSettings,
)
from .library_models import (
    ProductLibrary,
    LibrarySection,
    LibraryClause,
    LibraryTfidfIndex,
    LibrarySynonymOverride,
)

__all__ = [
    "AnalysisJob",
    "JobStatus",
    "StartAnalysisResponse",
    "JobStatusResponse",
    "AnalysisResultRowModel",
    "AnalysisResultsResponse",
    "UploadPreviewResponse",
    "FileUploadLimits",
    "UploadValidationError",
    "AnalysisSettings",
    # Library models
    "ProductLibrary",
    "LibrarySection",
    "LibraryClause",
    "LibraryTfidfIndex",
    "LibrarySynonymOverride",
]
