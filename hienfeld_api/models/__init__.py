"""
Models package for Hienfeld VB Converter API.

Contains:
- job.py: AnalysisJob dataclass and JobStatus enum
- requests.py: Pydantic request/response models
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
]
