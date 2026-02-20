"""
Pydantic request/response models for the API.

These models define the structure of API responses and provide
automatic validation and documentation.
"""

from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Upload constraints
# ---------------------------------------------------------------------------

class FileUploadLimits(BaseModel):
    """Constraints for file uploads."""
    max_file_size: int = 50 * 1024 * 1024  # 50 MB
    allowed_extensions: Set[str] = {".xlsx", ".xls", ".csv", ".pdf", ".docx", ".txt"}
    allowed_mimes: Set[str] = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",  # fallback for files we can't detect
    }


class UploadValidationError(Exception):
    """Raised when file upload validation fails."""
    pass


# ---------------------------------------------------------------------------
# Analysis settings validation
# ---------------------------------------------------------------------------

class AnalysisSettings(BaseModel):
    """Validated analysis settings from frontend."""
    cluster_accuracy: int = Field(default=90, ge=50, le=100)
    min_frequency: int = Field(default=20, ge=1, le=10000)
    window_size: int = Field(default=100, ge=10, le=500)
    use_conditions: bool = True
    use_window_limit: bool = True
    use_semantic: bool = True
    ai_enabled: bool = False
    analysis_mode: str = Field(default="balanced")
    extra_instruction: str = Field(default="", max_length=10000)

    @field_validator("analysis_mode")
    @classmethod
    def validate_analysis_mode(cls, v: str) -> str:
        allowed = {"fast", "balanced", "accurate"}
        if v.lower() not in allowed:
            raise ValueError(f"analysis_mode must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("cluster_accuracy")
    @classmethod
    def validate_cluster_accuracy(cls, v: int) -> int:
        if v % 5 != 0:
            raise ValueError("cluster_accuracy must be a multiple of 5")
        return v


class StartAnalysisResponse(BaseModel):
    """Response when starting a new analysis job."""
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Response for job status polling."""
    job_id: str
    status: str
    progress: int
    status_message: str
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class AnalysisResultRowModel(BaseModel):
    """Single row in analysis results."""
    cluster_id: str
    cluster_name: str
    frequency: int
    advice_code: str
    confidence: str
    reason: str
    reference_article: str
    original_text: str
    row_type: str
    parent_id: Optional[str] = None
    action_status: Optional[str] = None  # "✅ Afgerond", "🔲 Open", "🆕 Nieuw"


class AnalysisResultsResponse(BaseModel):
    """Full analysis results for a completed job."""
    job_id: str
    status: str
    stats: Optional[Dict[str, Any]]
    results: List[AnalysisResultRowModel]


class UploadPreviewResponse(BaseModel):
    """Response for file upload preview."""
    columns: List[str]
    row_count: int
    text_column: str
    policy_column: Optional[str]
