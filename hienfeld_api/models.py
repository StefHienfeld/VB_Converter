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


class JobStatus:
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJob:
    """In-memory job object for tracking analysis progress"""
    def __init__(self, id: str):
        self.id = id
        self.status = JobStatus.PENDING
        self.progress = 0
        self.status_message = "Wachten op start..."
        self.error: Optional[str] = None
        self.results: Optional[List[dict]] = None
        self.stats: Optional[dict] = None
        self.report_bytes: Optional[bytes] = None

    def update(self, progress: int = None, message: str = None, status: str = None):
        """Update job progress"""
        if progress is not None:
            self.progress = progress
        if message is not None:
            self.status_message = message
        if status is not None:
            self.status = status

    def complete(self, results: List[dict], stats: dict, report_bytes: bytes):
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        self.progress = 100
        self.status_message = "Analyse voltooid"
        self.results = results
        self.stats = stats
        self.report_bytes = report_bytes

    def fail(self, error: str):
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.error = error
        self.status_message = f"Fout: {error}"


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    status_message: str
    error: Optional[str] = None
    stats: Optional[dict] = None


class StartAnalysisResponse(BaseModel):
    """Response when analysis is started"""
    job_id: str
    status: str


class UploadPreviewResponse(BaseModel):
    """Response for upload preview"""
    columns: List[str]
    row_count: int
    text_column: str
    policy_column: Optional[str] = None


class AnalysisResultRowModel(BaseModel):
    """Single row in analysis results"""
    class Config:
        extra = "allow"  # Allow extra fields from analysis results


class AnalysisResultsResponse(BaseModel):
    """Response for full analysis results"""
    job_id: str
    status: str
    stats: dict
    results: List[AnalysisResultRowModel]
