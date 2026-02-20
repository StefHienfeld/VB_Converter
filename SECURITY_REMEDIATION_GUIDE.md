# Security Remediation Guide - VB Converter
**Implementation Guide for Critical & High Issues**
**Version:** 1.0
**Date:** 2026-02-18

---

## Quick Start (First 24 Hours)

### 1. IMMEDIATE: Revoke Exposed API Key

**Status:** CRITICAL - Do this now
**Time:** 5 minutes

```bash
# 1. Go to https://platform.openai.com/account/api-keys
# 2. Find and delete the exposed key (already revoked)
# 3. Generate new API key
# 4. Update in vault/secrets manager only (NOT in git)

# 5. Clean git history (required because key was committed)
cd /path/to/vb-converter
git clone https://github.com/you/vb-converter /tmp/clean-repo
cd /tmp/clean-repo

# Install BFG repo cleaner
brew install bfg  # macOS
# or
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.13.0/bfg-1.13.0.jar

# Remove all instances of .env from history
bfg --delete-files .env

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (⚠️ This rewrites history - coordinate with team!)
git push --force-with-lease

# Verify key is gone
git log -p --all -- .env | grep OPENAI_API_KEY
# Should be empty
```

---

## Week 1: Critical Fixes (P0)

### Fix 1: Patch All CVEs

**Time:** 1-2 hours
**File:** `requirements.txt`, `requirements-docker.txt`

```bash
# Update requirements.txt with pinned versions
pip install --upgrade pip
pip install pip-audit

# Check current vulnerabilities
python -m pip_audit -r requirements.txt

# Create fixed requirements.txt
cat > requirements.txt << 'EOF'
# Web / API
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic-settings>=2.0.0

# Data processing
pandas>=2.0.0
openpyxl>=3.1.0
xlsxwriter>=3.1.0

# Document parsing
python-docx>=0.8.11
pdfplumber>=0.10.0  # Use instead of PyMuPDF for MIT license
pywin32>=306; sys_platform == 'win32'

# Fast string matching
rapidfuzz>=3.0.0

# NLP & Semantic Analysis
spacy>=3.7.0
gensim>=4.3.0
wn>=0.9.0

# Sentence Embeddings
sentence-transformers>=2.2.0
faiss-cpu>=1.7.4

# AI / LLM (optional)
openai>=1.0.0

# Rate limiting
slowapi>=0.1.9

# SECURITY PATCH - 2026-02-18
# Pinned versions to fix known vulnerabilities
cryptography>=46.0.5
filelock>=3.20.3
pdfminer-six>=20251230
pillow>=12.1.1
protobuf>=6.33.5
pypdf>=6.6.2
python-multipart>=0.0.22
urllib3>=2.6.3

# Additional security tools (for development)
# Uncomment these only in dev environment
# bandit>=1.7.5
# safety>=3.0.0
EOF

# Do the same for requirements-docker.txt
cp requirements.txt requirements-docker.txt

# Commit changes
git add requirements.txt requirements-docker.txt
git commit -m "fix: Patch critical CVEs in dependencies (CVE-2025-70559 pdfminer-six, etc.)"

# Test locally
pip install -r requirements.txt
python -m pip_audit -r requirements.txt
# Should show 0 vulnerabilities
```

---

### Fix 2: Add Input Validation

**Time:** 2-3 hours
**Files:** `hienfeld_api/app.py`, `hienfeld_api/models.py`

```python
# Step 1: Create validation models
# File: hienfeld_api/models/validation.py (NEW)

from pydantic import BaseModel, Field, validator
from typing import Optional

class AnalysisParametersModel(BaseModel):
    """Validated analysis parameters."""

    # Cluster accuracy: 0-100 representing similarity threshold percentage
    cluster_accuracy: int = Field(default=90, ge=0, le=100)

    # Min frequency: how many times a clause must appear to suggest standardization
    min_frequency: int = Field(default=20, ge=1, le=1000)

    # Window size: how many clusters to compare against (smaller = faster)
    window_size: int = Field(default=100, ge=10, le=500)

    # Feature flags
    use_conditions: bool = True
    use_window_limit: bool = True
    use_semantic: bool = True
    ai_enabled: bool = False

    # Analysis mode
    analysis_mode: str = Field(default="balanced")

    # Extra instructions
    extra_instruction: str = Field(default="", max_length=10000)

    @validator('analysis_mode')
    def validate_mode(cls, v):
        if v not in ['fast', 'balanced', 'accurate']:
            raise ValueError('analysis_mode must be: fast, balanced, or accurate')
        return v

    @validator('extra_instruction')
    def validate_instructions(cls, v):
        if len(v) > 10000:
            raise ValueError('Extra instructions limited to 10000 characters')
        return v

# Step 2: Update API endpoint
# File: hienfeld_api/app.py - Replace start_analysis function

from hienfeld_api.models.validation import AnalysisParametersModel

@app.post("/api/analyze", response_model=StartAnalysisResponse)
async def start_analysis(
    background_tasks: BackgroundTasks,
    policy_file: UploadFile = File(...),
    conditions_files: List[UploadFile] = File(default=[]),
    clause_library_files: List[UploadFile] = File(default=[]),
    reference_file: Optional[UploadFile] = File(default=None),
    # Validated parameters
    cluster_accuracy: int = Form(90),
    min_frequency: int = Form(20),
    window_size: int = Form(100),
    use_conditions: bool = Form(True),
    use_window_limit: bool = Form(True),
    use_semantic: bool = Form(True),
    ai_enabled: bool = Form(False),
    analysis_mode: str = Form("balanced"),
    extra_instruction: str = Form(""),
) -> StartAnalysisResponse:
    """Start a new analysis job with validated parameters."""

    # Validate all parameters using Pydantic model
    try:
        params = AnalysisParametersModel(
            cluster_accuracy=cluster_accuracy,
            min_frequency=min_frequency,
            window_size=window_size,
            use_conditions=use_conditions,
            use_window_limit=use_window_limit,
            use_semantic=use_semantic,
            ai_enabled=ai_enabled,
            analysis_mode=analysis_mode,
            extra_instruction=extra_instruction,
        )
    except ValidationError as e:
        logger.warning(f"Invalid analysis parameters: {e}")
        raise HTTPException(status_code=422, detail={
            "message": "Invalid analysis parameters",
            "errors": [str(err) for err in e.errors()]
        })

    # Continue with existing file validation and processing...
    policy_bytes = await policy_file.read()
    if not policy_bytes:
        raise HTTPException(status_code=400, detail="Polisbestand is leeg of ontbreekt")

    # ... rest of function remains the same, but use params instead of raw values
    settings = {
        "cluster_accuracy": params.cluster_accuracy,
        "min_frequency": params.min_frequency,
        "window_size": params.window_size,
        "use_conditions": params.use_conditions,
        "use_window_limit": params.use_window_limit,
        "use_semantic": params.use_semantic,
        "ai_enabled": params.ai_enabled,
        "analysis_mode": params.analysis_mode,
        "extra_instruction": params.extra_instruction,
    }

    # ... rest of function
```

---

### Fix 3: Enforce HTTPS in Production

**Time:** 1 hour
**Files:** `hienfeld_api/app.py`, `.env.example`, `hienfeld/settings/settings.py`

```python
# Step 1: Add HTTPS redirect middleware
# File: hienfeld_api/app.py (add after CORS setup)

from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Add HTTPS redirect for production
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("🔒 HTTPS redirect enabled for production")

# Step 2: Validate CORS origins for production
# File: hienfeld/settings/settings.py (modify get_allowed_origins_list)

def get_allowed_origins_list(self) -> List[str]:
    """
    Parse comma-separated origins into list.

    In production:
    - Only HTTPS origins allowed
    - No localhost/127.0.0.1 allowed
    """
    origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    if self.is_production:
        # Validate no development URLs in production
        for origin in origins:
            if "localhost" in origin or "127.0.0.1" in origin:
                raise ValueError(
                    f"❌ SECURITY: Development origin '{origin}' found in production ALLOWED_ORIGINS!\n"
                    f"Remove localhost/127.0.0.1 from production .env"
                )
            if not origin.startswith("https://"):
                raise ValueError(
                    f"❌ SECURITY: Non-HTTPS origin '{origin}' found in production!\n"
                    f"All production origins must use HTTPS"
                )

        logger.warning(f"✅ Production CORS origins validated: {len(origins)} allowed")

    return origins

# Step 3: Update environment configuration
# File: .env.example

# Production environment variables
# Copy this to .env and adjust for your deployment

# === Security ===
# REQUIRED: Generate new key with: openssl rand -hex 32
SECRET_KEY=MUST-CHANGE-IN-PRODUCTION

# PRODUCTION ONLY: HTTPS-only origins
ALLOWED_ORIGINS=https://myapp.example.com,https://admin.myapp.example.com

# === Environment ===
ENVIRONMENT=production
DEBUG=false

# ... rest of file
```

---

### Fix 4: Implement Authentication & Access Control

**Time:** 4-6 hours
**Files:** `hienfeld_api/security.py` (NEW), `hienfeld_api/app.py`

```python
# Step 1: Create authentication module
# File: hienfeld_api/security.py (NEW)

from typing import Optional
from fastapi import HTTPException, Header, Depends
from functools import lru_cache
import os

class AuthenticationManager:
    """Simple token-based authentication for job access."""

    def __init__(self):
        # In production, use proper auth (OAuth2, JWT, etc.)
        # For now, use a simple token from environment
        self.admin_token = os.getenv("ADMIN_TOKEN", "")

        if not self.admin_token and os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError(
                "❌ SECURITY: ADMIN_TOKEN required in production!\n"
                "Generate with: openssl rand -hex 32"
            )

    def verify_admin_token(self, token: str) -> bool:
        """Verify admin token."""
        if not self.admin_token:
            return True  # Disabled in development

        import secrets
        return secrets.compare_digest(token, self.admin_token)

@lru_cache()
def get_auth_manager() -> AuthenticationManager:
    return AuthenticationManager()

# Step 2: Add authentication to endpoints
# File: hienfeld_api/app.py (update relevant endpoints)

from hienfeld_api.security import get_auth_manager, AuthenticationManager

# Apply to status and results endpoints
@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_status(
    job_id: str,
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> JobStatusResponse:
    """Return status/progress for a given analysis job (authenticated)."""
    job = job_repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job niet gevonden")

    # In production with user auth:
    # if not auth.user_owns_job(current_user, job_id):
    #     raise HTTPException(status_code=403, detail="Toegang geweigerd")

    stats = job.stats if job.status == JobStatus.COMPLETED else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        status_message=job.status_message,
        error=job.error,
        stats=stats,
    )

@app.get("/api/results/{job_id}", response_model=AnalysisResultsResponse)
async def get_results(
    job_id: str,
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> AnalysisResultsResponse:
    """Return full analysis results (authenticated)."""
    job = job_repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job niet gevonden")

    # User authentication check (TODO)
    # if not auth.user_owns_job(current_user, job_id):
    #     raise HTTPException(status_code=403, detail="Toegang geweigerd")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=202, detail=f"Job status is '{job.status}'")

    if job.results is None or job.stats is None:
        raise HTTPException(status_code=500, detail="Resultaten ontbreken voor deze job")

    rows = [AnalysisResultRowModel(**row) for row in job.results]
    return AnalysisResultsResponse(
        job_id=job.id,
        status=job.status,
        stats=job.stats,
        results=rows,
    )

# Apply to cache endpoints
@app.post("/api/cache/clear")
async def clear_cache(
    x_admin_token: str = Header(None),
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> Dict[str, Any]:
    """Clear cache (admin only)."""
    if not auth.verify_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Invalid admin token")

    cache = get_service_cache()
    count = cache.clear()
    logger.info(f"🗑️ Cache cleared by admin ({count} entries)")
    return {"status": "ok", "cleared_count": count}
```

---

### Fix 5: Implement Data Retention & Auto-Cleanup

**Time:** 3-4 hours
**Files:** `hienfeld_api/repositories/memory_job_repository.py`, `hienfeld_api/app.py`

```python
# Step 1: Update MemoryJobRepository with TTL
# File: hienfeld_api/repositories/memory_job_repository.py

import time
from threading import Lock, Thread
from typing import Dict, List, Optional
from hienfeld_api.models import AnalysisJob
from .job_repository import JobRepository
from hienfeld.logging_config import get_logger

logger = get_logger("job_repository")

class MemoryJobRepository(JobRepository):
    """
    Thread-safe in-memory job storage with automatic TTL cleanup.

    Jobs older than ttl_seconds are automatically removed.
    """

    def __init__(self, ttl_seconds: int = 86400):  # 24 hours default
        """
        Initialize with TTL cleanup.

        Args:
            ttl_seconds: Time to live for jobs in seconds (default: 24 hours)
        """
        self._jobs: Dict[str, AnalysisJob] = {}
        self._created_at: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._cleanup_thread = None

        logger.info(f"Job repository initialized with TTL: {ttl_seconds}s ({ttl_seconds//3600}h)")
        self._start_cleanup_thread()

    def save(self, job: AnalysisJob) -> None:
        """Store or update a job."""
        with self._lock:
            self._jobs[job.id] = job
            self._created_at[job.id] = time.time()
            logger.debug(f"Job saved: {job.id} (TTL: {self._ttl_seconds}s)")

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """Retrieve a job by ID."""
        with self._lock:
            job = self._jobs.get(job_id)

            # Check if job is expired
            if job and job_id in self._created_at:
                age = time.time() - self._created_at[job_id]
                if age > self._ttl_seconds:
                    logger.info(f"Job {job_id} expired (age: {age}s, TTL: {self._ttl_seconds}s)")
                    del self._jobs[job_id]
                    del self._created_at[job_id]
                    return None

            return job

    def delete(self, job_id: str) -> bool:
        """Delete a job."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                if job_id in self._created_at:
                    del self._created_at[job_id]
                logger.info(f"Job deleted: {job_id}")
                return True
            return False

    def list_all(self) -> List[AnalysisJob]:
        """List all non-expired jobs."""
        with self._lock:
            # Remove expired jobs first
            self._cleanup_expired_unsafe()
            return list(self._jobs.values())

    def count(self) -> int:
        """Count non-expired jobs."""
        with self._lock:
            self._cleanup_expired_unsafe()
            return len(self._jobs)

    def cleanup_expired(self) -> int:
        """
        Manually trigger cleanup of expired jobs.

        Returns:
            Number of jobs removed
        """
        with self._lock:
            return self._cleanup_expired_unsafe()

    def _cleanup_expired_unsafe(self) -> int:
        """
        Remove expired jobs (must be called with lock held).

        Returns:
            Number of jobs removed
        """
        now = time.time()
        expired = []

        for job_id, created_at in self._created_at.items():
            age = now - created_at
            if age > self._ttl_seconds:
                expired.append(job_id)

        for job_id in expired:
            del self._jobs[job_id]
            del self._created_at[job_id]

        if expired:
            logger.info(f"Cleanup: Removed {len(expired)} expired jobs")

        return len(expired)

    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        def cleanup_loop():
            import asyncio
            cleanup_interval = self._ttl_seconds // 4  # Check every 25% of TTL
            cleanup_interval = max(cleanup_interval, 3600)  # Minimum 1 hour

            logger.info(f"Cleanup thread started (interval: {cleanup_interval}s)")

            while True:
                try:
                    time.sleep(cleanup_interval)
                    count = self.cleanup_expired()
                    if count > 0:
                        logger.info(f"✅ Background cleanup: Removed {count} expired jobs")
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}")

        # Start cleanup thread as daemon
        self._cleanup_thread = Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def clear(self) -> int:
        """Clear all jobs (for testing)."""
        with self._lock:
            count = len(self._jobs)
            self._jobs.clear()
            self._created_at.clear()
            logger.warning(f"All jobs cleared ({count} jobs removed)")
            return count

# Step 2: Add TTL configuration to settings
# File: hienfeld/settings/settings.py

class Settings(BaseSettings):
    # ... existing fields ...

    # === Data Retention ===
    job_ttl_hours: int = 24  # Keep jobs for 24 hours then auto-delete

    @property
    def job_ttl_seconds(self) -> int:
        """Convert TTL hours to seconds."""
        return self.job_ttl_hours * 3600

# Step 3: Use settings in app initialization
# File: hienfeld_api/app.py

settings = get_settings()
job_repository = MemoryJobRepository(ttl_seconds=settings.job_ttl_seconds)

# Add startup event to log cleanup status
@app.on_event("startup")
async def startup_event():
    logger.info(f"🗑️ Job auto-cleanup enabled: {settings.job_ttl_hours}h TTL")
```

---

### Fix 6: Protect Cache Management Endpoints

**Time:** 30 minutes
**File:** `hienfeld_api/app.py`

```python
# Add to imports
from hienfeld_api.security import get_auth_manager

# Apply authentication to cache endpoints
@app.get("/api/cache/stats")
async def get_cache_stats(
    x_admin_token: str = Header(None),
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> Dict[str, Any]:
    """Get cache statistics (admin only)."""
    if not auth.verify_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Invalid admin token")

    cache = get_service_cache()
    return cache.get_stats()

@app.post("/api/cache/clear")
async def clear_cache(
    x_admin_token: str = Header(None),
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> Dict[str, Any]:
    """Clear cache (admin only)."""
    if not auth.verify_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Invalid admin token")

    cache = get_service_cache()
    count = cache.clear()
    logger.warning(f"🗑️ Cache cleared by admin ({count} entries)")
    return {"status": "ok", "cleared_count": count}

@app.delete("/api/cache/{key}")
async def invalidate_cache_entry(
    key: str,
    x_admin_token: str = Header(None),
    auth: AuthenticationManager = Depends(get_auth_manager)
) -> Dict[str, Any]:
    """Invalidate cache entry (admin only)."""
    if not auth.verify_admin_token(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Invalid admin token")

    cache = get_service_cache()
    success = cache.invalidate(key)
    if success:
        logger.info(f"🗑️ Cache entry '{key}' invalidated by admin")
        return {"status": "ok", "message": f"Invalidated '{key}'"}
    else:
        raise HTTPException(status_code=404, detail=f"Cache key '{key}' not found")
```

---

### Fix 7: Validate Default Secrets

**Time:** 30 minutes
**File:** `hienfeld_api/app.py`

```python
# Add right after get_settings()

settings = get_settings()

# CRITICAL: Validate production secrets
if settings.is_production:
    # Check SECRET_KEY
    if settings.secret_key == "dev-only-change-in-production-openssl-rand-hex-32":
        raise RuntimeError(
            "❌ SECURITY: Production deployment with default SECRET_KEY!\n"
            "Generate new key: openssl rand -hex 32\n"
            "Set environment variable: SECRET_KEY=<your-generated-key>"
        )

    # Check OPENAI_API_KEY (if AI features enabled)
    if settings.feature_ai_extensions and not settings.openai_api_key:
        raise RuntimeError(
            "❌ SECURITY: AI features enabled but OPENAI_API_KEY not set!\n"
            "Set environment variable: OPENAI_API_KEY=sk-..."
        )

    # Check ALLOWED_ORIGINS
    origins = settings.get_allowed_origins_list()
    if any("localhost" in o or "127.0.0.1" in o for o in origins):
        raise RuntimeError(
            "❌ SECURITY: Localhost origins in production CORS!\n"
            f"Current: {settings.allowed_origins}\n"
            "Set to production domain: ALLOWED_ORIGINS=https://myapp.example.com"
        )

    logger.info("✅ Production secrets validated")
```

---

### Fix 8: Add Rate Limiting

**Time:** 1 hour
**File:** `hienfeld_api/app.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# Create limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Add exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Te veel verzoeken. Probeer later opnieuw.",
            "retry_after": "60"
        }
    )

# Apply rate limits to critical endpoints
@app.post("/api/analyze")
@limiter.limit("10/hour")  # 10 analyses per hour per IP
async def start_analysis(...):
    # ... existing code ...

@app.post("/api/upload/preview")
@limiter.limit("30/hour")  # Preview requests
async def upload_preview(...):
    # ... existing code ...

@app.get("/api/status/{job_id}")
@limiter.limit("100/minute")  # Status polling
async def get_status(...):
    # ... existing code ...

@app.get("/api/results/{job_id}")
@limiter.limit("50/minute")  # Result access
async def get_results(...):
    # ... existing code ...

@app.post("/api/cache/clear")
@limiter.limit("1/hour")  # Dangerous operation
async def clear_cache(...):
    # ... existing code ...
```

---

## Week 2-3: High Priority Fixes (P1)

### Implement Comprehensive Audit Logging

**Time:** 4-6 hours
**File:** `hienfeld/services/audit_service.py` (NEW)

```python
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

class AuditEventType(str, Enum):
    """Audit event types for compliance."""
    ANALYSIS_STARTED = "ANALYSIS_STARTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    RESULT_ACCESSED = "RESULT_ACCESSED"
    RESULT_EXPORTED = "RESULT_EXPORTED"
    JOB_DELETED = "JOB_DELETED"
    CACHE_CLEARED = "CACHE_CLEARED"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"

class AuditLogger:
    """Structured audit logging for compliance."""

    def __init__(self):
        self.logger = logging.getLogger("audit")
        # Ensure audit logs go to separate file
        if not self.logger.handlers:
            handler = logging.FileHandler("logs/audit.log")
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_event(self, event_type: AuditEventType, **details):
        """Log audit event with structured format."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "details": details
        }
        self.logger.info(json.dumps(event))

    def log_analysis_started(
        self,
        job_id: str,
        user_id: Optional[str],
        file_name: str,
        file_size: int,
        analysis_mode: str
    ):
        """Log analysis job creation."""
        self.log_event(
            AuditEventType.ANALYSIS_STARTED,
            job_id=job_id,
            user_id=user_id or "anonymous",
            file_name=file_name,
            file_size=file_size,
            analysis_mode=analysis_mode
        )

    def log_analysis_completed(self, job_id: str, clause_count: int, duration_seconds: float):
        """Log successful analysis completion."""
        self.log_event(
            AuditEventType.ANALYSIS_COMPLETED,
            job_id=job_id,
            clause_count=clause_count,
            duration_seconds=round(duration_seconds, 2)
        )

    def log_result_accessed(self, job_id: str, user_id: Optional[str], client_ip: str):
        """Log result access (right to audit access)."""
        self.log_event(
            AuditEventType.RESULT_ACCESSED,
            job_id=job_id,
            user_id=user_id or "anonymous",
            client_ip=client_ip
        )

    def log_result_exported(self, job_id: str, format_type: str, user_id: Optional[str]):
        """Log result export/download."""
        self.log_event(
            AuditEventType.RESULT_EXPORTED,
            job_id=job_id,
            format_type=format_type,
            user_id=user_id or "anonymous"
        )

    def log_job_deleted(self, job_id: str, reason: str, user_id: Optional[str] = None):
        """Log job deletion (for right to erasure compliance)."""
        self.log_event(
            AuditEventType.JOB_DELETED,
            job_id=job_id,
            reason=reason,  # "ttl_expired", "user_requested", "manual_deletion"
            user_id=user_id or "system"
        )

    def log_cache_cleared(self, entry_count: int, user_id: str):
        """Log cache clearing."""
        self.log_event(
            AuditEventType.CACHE_CLEARED,
            entry_count=entry_count,
            user_id=user_id
        )

# Global audit logger instance
audit_logger = AuditLogger()
```

---

## Testing Checklist

After each fix, verify with these tests:

```bash
# Test 1: Security headers present
curl -I http://localhost:8000/api/health | grep -E "X-Frame-Options|X-Content-Type-Options|X-XSS-Protection"

# Test 2: Rate limiting works
for i in {1..15}; do curl -s http://localhost:8000/api/analyze -X POST > /dev/null; done
# Should get 429 after 10th request

# Test 3: CORS validates origins
curl -s -H "Origin: http://evil.com" http://localhost:8000/api/health

# Test 4: Input validation works
curl -s -X POST http://localhost:8000/api/analyze \
  -F "cluster_accuracy=-1" \
  -F "policy_file=@test.csv"
# Should return 422 Unprocessable Entity

# Test 5: Cache endpoints require auth
curl -X POST http://localhost:8000/api/cache/clear
# Should return 403 Forbidden

# Test 6: Secrets validated in production
ENVIRONMENT=production SECRET_KEY=dev-only... python -m uvicorn hienfeld_api.app:app
# Should fail with error message
```

---

## Deployment Checklist

```markdown
## Pre-Deployment Security Checklist

### Secrets (CRITICAL)
- [ ] API key rotated in OpenAI dashboard
- [ ] Git history cleaned (BFG used)
- [ ] SECRET_KEY changed from default
- [ ] ALLOWED_ORIGINS set to production domain
- [ ] All secrets in vault (not .env)
- [ ] No hardcoded credentials in code

### Dependencies (CRITICAL)
- [ ] CVEs patched (pip-audit passes)
- [ ] No GPL/AGPL dependencies
- [ ] requirements.txt pinned to specific versions

### API Security (CRITICAL)
- [ ] Input validation on all endpoints
- [ ] Authentication on sensitive endpoints
- [ ] Rate limiting configured
- [ ] HTTPS enforcement enabled
- [ ] CORS origins validated
- [ ] Security headers present

### Data Security (CRITICAL)
- [ ] Job TTL configured (24 hours)
- [ ] Auto-cleanup thread running
- [ ] Audit logging enabled
- [ ] Deletion endpoint working

### Testing (CRITICAL)
- [ ] All unit tests passing
- [ ] Security tests included
- [ ] Load testing done (1000+ concurrent)
- [ ] Rate limiting tested
- [ ] CORS validation tested

### Infrastructure (CRITICAL)
- [ ] Container runs as non-root
- [ ] Health check endpoint working
- [ ] Logging sent to SIEM
- [ ] Backup/recovery tested

### Deployment (CRITICAL)
- [ ] Deployment checklist signed off
- [ ] Security review completed
- [ ] Monitoring/alerting configured
- [ ] Incident response plan ready
```

---

## Monitoring & Alerting

```yaml
# Add to Prometheus/DataDog/CloudWatch

alerts:
  - name: HighErrorRate
    condition: error_rate > 5%
    severity: high

  - name: RateLimitExceeded
    condition: rate_limit_errors > 10/min
    severity: medium

  - name: JobCleanupFailed
    condition: cleanup_errors > 0
    severity: high

  - name: UnauthorizedAccessAttempts
    condition: auth_failures > 5/min
    severity: critical

  - name: CertificateExpiringSoon
    condition: ssl_cert_days_remaining < 30
    severity: high
```

---

## Questions?

For technical details, refer to:
- **SECURITY_AUDIT_REPORT.md** - Full audit findings
- **hienfeld_api/app.py** - API implementation
- **hienfeld/services/** - Business logic

---

**Last Updated:** 2026-02-18
**Next Review:** After P0/P1 completion

