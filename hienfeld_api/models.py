# hienfeld_api/models.py
"""
Pydantic models for request validation and response serialization.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum


class AnalysisMode(str, Enum):
    """Analysis mode options"""
    FAST = "fast"
    BALANCED = "balanced"
    ACCURATE = "accurate"


class AnalysisSettings(BaseModel):
    """Validated analysis settings with constraints"""

    cluster_accuracy: int = Field(
        default=90,
        ge=80,
        le=100,
        description="Clustering similarity threshold (80-100%)"
    )

    min_frequency: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Minimum frequency for standardization (1-1000)"
    )

    window_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Clustering window size (10-1000)"
    )

    analysis_mode: AnalysisMode = Field(
        default=AnalysisMode.BALANCED,
        description="Analysis mode: fast, balanced, or accurate"
    )

    ai_enabled: bool = Field(
        default=True,
        description="Enable AI-powered semantic matching"
    )

    use_conditions: bool = Field(
        default=True,
        description="Use policy conditions for matching"
    )

    use_semantic: bool = Field(
        default=True,
        description="Enable semantic similarity features"
    )

    extra_instruction: Optional[str] = Field(
        default="",
        max_length=10000,
        description="Custom analysis instructions"
    )

    @validator('cluster_accuracy')
    def validate_accuracy(cls, v):
        """Ensure cluster accuracy is reasonable"""
        if v < 80:
            raise ValueError('Cluster accuracy must be at least 80% for meaningful results')
        return v

    @validator('window_size')
    def validate_window_size(cls, v, values):
        """Ensure window size makes sense for clustering"""
        if v < 10:
            raise ValueError('Window size too small - minimum 10 for effective clustering')
        return v

    @validator('extra_instruction')
    def validate_instruction(cls, v):
        """Clean and validate custom instructions"""
        if v:
            v = v.strip()
            if len(v) > 10000:
                raise ValueError('Custom instructions too long (max 10000 characters)')
        return v

    class Config:
        use_enum_values = True


class FileUploadLimits(BaseModel):
    """File upload constraints for security"""

    max_file_size: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="Maximum file size in bytes"
    )

    max_row_count: int = Field(
        default=50000,
        description="Maximum number of rows to prevent memory issues"
    )

    allowed_extensions: List[str] = Field(
        default=['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.txt'],
        description="Allowed file extensions"
    )

    # MIME types for magic byte validation
    allowed_mimes: dict = Field(
        default={
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/vnd.ms-excel': '.xls',
            'text/csv': '.csv',
            'text/plain': '.csv',  # CSV often detected as text/plain
            'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'text/plain': '.txt',
        },
        description="Allowed MIME types for uploaded files"
    )

    class Config:
        frozen = True  # Immutable


class UploadValidationError(BaseModel):
    """Error details for upload validation failures"""
    error_type: str
    message: str
    details: dict = {}


class JobSubmissionResponse(BaseModel):
    """Response when analysis job is submitted"""
    job_id: str
    status: str
    message: str = "Analysis started"


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    status_message: str
    error: Optional[str] = None
    stats: Optional[dict] = None
