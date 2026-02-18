# Quick Fix Guide - DevOps Audit Action Items
## Hienfeld VB Converter - February 2026

---

## CRITICAL: P0 Actions (Do This Week)

### 1. Remove Exposed API Keys (2 hours)

**Step 1: Revoke the API Key**
```bash
# In OpenAI console:
# 1. Go to https://platform.openai.com/account/api-keys
# 2. Click on the exposed key
# 3. Click "Delete key"
# 4. Generate a new API key
# 5. Store it securely (password manager, not in code!)
```

**Step 2: Remove from Git History**
```bash
# Option 1: Using git-filter-branch (nuclear option - force push required)
cd "C:\Users\Stef\Desktop\Vb agent"
git filter-branch --tree-filter 'rm -f .env' HEAD
git push origin main --force

# Option 2: Using BFG Repo-Cleaner (faster, safer)
# Download from https://rtyley.github.io/bfg-repo-cleaner/
bfg --delete-files .env
git reflog expire --expire=now --all
git gc --prune=now
git push origin main --force
```

**Step 3: Update .gitignore**
```bash
# Edit .gitignore
cat >> .gitignore << 'EOF'

# Environment files (NEVER COMMIT)
.env
.env.local
.env.*.local
*.env

# Keep template
!.env.example
EOF

git add .gitignore
git commit -m "chore: Add .env to gitignore to prevent secret leaks"
```

**Step 4: Create .env.example**
```bash
cat > .env.example << 'EOF'
# === Environment ===
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# === OpenAI API (for AI analysis features) ===
# Get key from https://platform.openai.com/account/api-keys
OPENAI_API_KEY=sk-proj-xxx-your-key-here
LLM_MODEL=gpt-4o-mini

# === Security ===
# Generate with: openssl rand -hex 32
SECRET_KEY=your-secret-key-here-min-32-chars
EOF

git add .env.example
git commit -m "chore: Add .env.example template"
```

**Step 5: Verify (Important!)**
```bash
# Verify .env is not tracked
git ls-files | grep ".env"
# Should only show: .env.example

# Verify secrets removed
git log --source --all -p | grep "sk-proj"
# Should show no matches
```

---

### 2. Pin Python Dependencies (1-2 hours)

**Current Problem:**
```
# ❌ Bad: Can install different versions over time
fastapi>=0.115.0
pandas>=2.0.0
spacy>=3.7.0
```

**Solution: Create Pinned requirements.txt**

```bash
cd "C:\Users\Stef\Desktop\Vb agent"

# Freeze current environment (get exact versions)
pip freeze > requirements.txt

# Or use pip-tools for more control:
pip install pip-tools

# Create requirements.in (source file)
cat > requirements.in << 'EOF'
# Core
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic-settings>=2.0.0

# Data processing
pandas>=2.0.0
openpyxl>=3.1.0
xlsxwriter>=3.1.0

# Document parsing
python-docx>=0.8.11
PyMuPDF>=1.23.0
pdfplumber>=0.10.0
pywin32>=306; sys_platform == 'win32'

# NLP & ML
rapidfuzz>=3.0.0
spacy>=3.7.0
gensim>=4.3.0
wn>=0.9.0
sentence-transformers>=2.2.0
faiss-cpu>=1.7.4

# AI/LLM
openai>=1.0.0

# Rate limiting
slowapi
EOF

# Generate pinned requirements.txt
pip-compile requirements.in

# Commit both
git add requirements.in requirements.txt
git commit -m "chore: Pin Python dependency versions for reproducibility"
```

**Step 6: Update CI/CD**
```bash
# Edit .github/workflows/ci.yml
# Change line 57 from:
#   pip install -r requirements-docker.txt
# To:
#   pip install -r requirements-docker.txt --no-deps
# (ensures versions are respected)
```

---

### 3. Fix CI Linting Enforcement (30 minutes)

**Problem:** Linting failures don't block CI

**Fix:**
```yaml
# Edit .github/workflows/ci.yml

# Line 37: Change
- name: Run Black (check only)
  run: black --check --line-length 120 hienfeld/ hienfeld_api/
  continue-on-error: true  # ❌ DELETE THIS LINE

# To:
- name: Run Black (check only)
  run: black --check --line-length 120 hienfeld/ hienfeld_api/
  # ✅ No continue-on-error = will fail if code isn't formatted

# Line 121: Change
- name: Run ESLint
  run: npm run lint
  continue-on-error: true  # ❌ DELETE THIS LINE

# To:
- name: Run ESLint
  run: npm run lint
  # ✅ Will fail if linting errors exist
```

**Then commit:**
```bash
git add .github/workflows/ci.yml
git commit -m "chore: Make linting enforcement required in CI"
```

---

## P1 Actions (Next 2-3 Weeks)

### 4. Implement API Key Authentication (2-3 days)

**Add to hienfeld/settings/settings.py:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...

    # Security
    api_key: str = ""  # Set via environment variable
    api_key_enabled: bool = True

    class Config:
        env_file = ".env"
```

**Create hienfeld_api/middleware/auth.py:**

```python
from fastapi import HTTPException, status, Header
from typing import Optional
from hienfeld.settings import get_settings

async def verify_api_key(
    x_api_key: Optional[str] = Header(None)
) -> str:
    """Verify API key from request header."""
    settings = get_settings()

    if not settings.api_key_enabled:
        return ""  # Auth disabled (development)

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-API-Key header"
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    return x_api_key
```

**Update hienfeld_api/app.py:**

```python
from fastapi import Depends
from hienfeld_api.middleware.auth import verify_api_key

@app.post("/api/analyze", response_model=StartAnalysisResponse)
async def start_analysis(
    api_key: str = Depends(verify_api_key),
    # ... rest of parameters ...
):
    """Start analysis job (requires API key)."""
    # ... existing implementation ...
```

**Update .env:**

```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: example_5TN9_kL2mP_vQ3rS4tU5_wX6yZ7aB8cD

# Add to .env:
API_KEY_ENABLED=true
API_KEY=example_5TN9_kL2mP_vQ3rS4tU5_wX6yZ7aB8cD
```

**Update .env.example:**

```bash
# Security
API_KEY_ENABLED=false
API_KEY=your-secret-api-key-here-minimum-32-chars
```

**Test:**

```bash
# Without API key
curl -X POST http://localhost:8000/api/analyze
# Response: 403 Forbidden: "Missing X-API-Key header"

# With valid API key
curl -H "X-API-Key: example_5TN9_kL2mP_vQ3rS4tU5_wX6yZ7aB8cD" \
  -X POST http://localhost:8000/api/analyze \
  -F "policy_file=@policy.xlsx"
# Should work
```

---

### 5. Add Test Coverage Enforcement (1-2 days)

**Install pytest-cov:**

```bash
pip install pytest-cov
```

**Update .github/workflows/ci.yml:**

```yaml
- name: Run tests with coverage
  run: |
    pytest tests/ \
      --cov=hienfeld \
      --cov=hienfeld_api \
      --cov-report=term-missing \
      --cov-report=xml \
      --cov-fail-under=30
  # Start at 30%, gradually increase to 70%
```

**Create coverage baseline:**

```bash
cd "C:\Users\Stef\Desktop\Vb agent"

# Run tests and see current coverage
pytest tests/ --cov=hienfeld --cov=hienfeld_api --cov-report=term-missing

# Output will show:
# Name                              Stmts   Miss  Cover   Missing
# ─────────────────────────────────────────────────────────────
# hienfeld/services/__init__.py         0      0   100%
# hienfeld/services/analysis_service.py  1376  1100  20%   40-50, 120-150, ...

# Add report to CI artifacts:
```

**Update requirements.txt:**

```
pytest-cov>=4.1.0
```

**Commit:**

```bash
git add .github/workflows/ci.yml requirements.txt
git commit -m "chore: Add test coverage enforcement (30% threshold)"
```

---

### 6. Migrate to Poetry (2-3 days)

**Install Poetry:**

```bash
curl -sSL https://install.python-poetry.org | python3 -
# Or: pip install poetry
```

**Create pyproject.toml:**

```bash
cd "C:\Users\Stef\Desktop\Vb agent"

poetry init --no-interaction \
  --name vb-converter \
  --description "Hienfeld VB Converter - Insurance policy analysis" \
  --author "Your Team"

# This creates pyproject.toml
```

**Add dependencies:**

```bash
# From requirements.txt
poetry add fastapi==0.119.0 uvicorn==0.34.0 pandas==2.2.0

# Or copy exact versions from requirements.txt:
cat requirements.txt | while read line; do
  if [[ ! $line =~ ^# ]] && [[ ! -z $line ]]; then
    poetry add "$line"
  fi
done
```

**Generate lock file:**

```bash
poetry lock
# Creates poetry.lock (commit this!)

# Export for Docker:
poetry export -f requirements.txt --output requirements.txt --without dev
poetry export -f requirements.txt --output requirements-docker.txt --without dev
```

**Update .github/workflows/ci.yml:**

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: ${{ env.PYTHON_VERSION }}
    cache: poetry  # Changed from 'pip'

- name: Install dependencies
  run: poetry install
```

**Update docker-compose.yml:**

```dockerfile
# In Dockerfile.backend
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-directory
```

**Commit:**

```bash
git add pyproject.toml poetry.lock .github/workflows/ci.yml
git commit -m "feat: Migrate to Poetry for dependency management"
```

---

### 7. Add PostgreSQL (1-2 weeks)

**Step 1: Add SQLAlchemy & psycopg2 to dependencies:**

```bash
poetry add sqlalchemy psycopg2-binary alembic
```

**Step 2: Create database models (hienfeld_api/models/database.py):**

```python
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./test.db"  # Default to SQLite for development
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    progress = Column(Integer, default=0)
    policy_filename = Column(String(255), nullable=False)
    results = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AnalysisJob {self.id} ({self.status})>"

# Create tables on startup
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 3: Create database repository (hienfeld_api/repositories/postgres_job_repository.py):**

```python
from sqlalchemy.orm import Session
from hienfeld_api.models import AnalysisJob
from hienfeld_api.models.database import AnalysisJobModel
from .job_repository import JobRepository
from typing import Optional, List
from datetime import datetime

class PostgresJobRepository(JobRepository):
    """PostgreSQL-backed job repository."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, job: AnalysisJob) -> None:
        """Save or update a job."""
        model = AnalysisJobModel(
            id=job.id,
            status=job.status.value,
            progress=job.progress,
            policy_filename=job.policy_filename,
            results=job.results,
            error_message=job.error_message,
            updated_at=datetime.utcnow(),
            completed_at=job.completed_at,
        )
        self.db.merge(model)
        self.db.commit()

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        """Get a job by ID."""
        model = self.db.query(AnalysisJobModel).filter(
            AnalysisJobModel.id == job_id
        ).first()
        if not model:
            return None
        return self._to_domain(model)

    def delete(self, job_id: str) -> bool:
        """Delete a job."""
        job = self.db.query(AnalysisJobModel).filter(
            AnalysisJobModel.id == job_id
        ).first()
        if job:
            self.db.delete(job)
            self.db.commit()
            return True
        return False

    def list_all(self) -> List[AnalysisJob]:
        """List all jobs."""
        models = self.db.query(AnalysisJobModel).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: AnalysisJobModel) -> AnalysisJob:
        """Convert database model to domain object."""
        from hienfeld_api.models import JobStatus
        return AnalysisJob(
            id=model.id,
            status=JobStatus(model.status),
            progress=model.progress,
            policy_filename=model.policy_filename,
            results=model.results or [],
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )
```

**Step 4: Update hienfeld_api/app.py:**

```python
from hienfeld_api.models.database import get_db
from hienfeld_api.repositories import PostgresJobRepository
from sqlalchemy.orm import Session

# Use dependency injection for database
@app.get("/api/status/{job_id}")
async def get_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    repo = PostgresJobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

**Step 5: Setup Alembic for migrations:**

```bash
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

**Step 6: Update docker-compose.yml:**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: vb-converter-db
    environment:
      POSTGRES_DB: vb_converter
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - vb-network

  backend:
    # ... existing config ...
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD:-postgres}@postgres:5432/vb_converter
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:

networks:
  vb-network:
```

**Step 7: Add to .env:**

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vb_converter
DB_PASSWORD=postgres
```

---

### 8. Add Rate Limiting (1-2 days)

**Install slowapi (already in requirements.txt):**

```bash
pip install slowapi
```

**Create middleware (hienfeld_api/middleware/rate_limit.py):**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)

def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )
```

**Update hienfeld_api/app.py:**

```python
from hienfeld_api.middleware.rate_limit import limiter, rate_limit_error_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_error_handler)

@app.post("/api/analyze")
@limiter.limit("5/minute")
async def start_analysis(
    request: Request,
    # ... rest of parameters ...
):
    """Start analysis job (5 per minute per IP)."""
    # Implementation
```

**Update .env:**

```
RATE_LIMIT_ENABLED=true
RATE_LIMIT_ANALYZE=5/minute
```

---

## Verification Checklist

After completing P0 items:

- [ ] API keys removed from git history
- [ ] .env not tracked by git
- [ ] .env.example created
- [ ] Dependencies pinned to exact versions
- [ ] CI linting is required (no continue-on-error)
- [ ] All tests pass
- [ ] No secrets in repository

Run this to verify:

```bash
cd "C:\Users\Stef\Desktop\Vb agent"

# Check git history for secrets
git log --source --all -p | grep -i "sk-proj\|openai_api_key" || echo "✓ No secrets found"

# Check tracked files
git ls-files | grep "\.env" || echo "✓ .env not tracked"

# Check .gitignore
grep "\.env" .gitignore && echo "✓ .env in .gitignore"

# Check for pinned versions
grep "==" requirements.txt | wc -l
# Should show: 18 dependencies with exact versions

# Run tests
pytest tests/ -v
```

---

## Next Steps

1. **Complete P0 items** (1 week)
   - Remove secrets
   - Pin versions
   - Fix CI

2. **Plan P1 items** (2-3 weeks)
   - API authentication
   - PostgreSQL
   - Test coverage
   - Poetry migration

3. **Assign owners** and create GitHub issues
   - Each P1 item = 1 GitHub issue
   - Assign to team members
   - Set due dates

4. **Weekly sync** to track progress
   - Review completed items
   - Unblock issues
   - Adjust timeline if needed

---

**Last Updated:** February 18, 2026
**Status:** Ready for Implementation
